import os
import json
from datetime import datetime
from typing import Callable
from loguru import logger
from fastapi import WebSocket

from prompts import prompt_loader
from .live2d_model import Live2dModel
from .asr.asr_interface import ASRInterface
from .tts.tts_interface import TTSInterface
from .vad.vad_interface import VADInterface
from .agent.agents.agent_interface import AgentInterface
from .translate.translate_interface import TranslateInterface

from .mcpp.server_registry import ServerRegistry
from .mcpp.tool_manager import ToolManager
from .mcpp.mcp_client import MCPClient
from .mcpp.tool_executor import ToolExecutor
from .mcpp.tool_adapter import ToolAdapter

from .asr.asr_factory import ASRFactory
from .tts.tts_factory import TTSFactory
from .vad.vad_factory import VADFactory
from .agent.agent_factory import AgentFactory
from .translate.translate_factory import TranslateFactory

from .config_manager import (
    Config,
    AgentConfig,
    CharacterConfig,
    SystemConfig,
    ASRConfig,
    TTSConfig,
    VADConfig,
    TranslatorConfig,
    read_yaml,
    validate_config,
)

# === 进程级共享记忆单例（关键：避免每会话独立实例导致 reset/蒸馏不生效、旧缓存复活）===
_shared_memory_hub = None
_shared_persona_distiller = None
_shared_mem_dir = None


def _get_shared_memory_hub(mem_dir: str):
    """进程级唯一 MemoryHub。reset 时调用 _reset_shared_memory 重建，所有会话即时生效。"""
    global _shared_memory_hub, _shared_mem_dir
    if _shared_memory_hub is None or _shared_mem_dir != mem_dir:
        from .memory_hub import MemoryHub
        _shared_memory_hub = MemoryHub(mem_dir)
        _shared_mem_dir = mem_dir
    return _shared_memory_hub


def _get_shared_persona_distiller(mem_dir: str):
    """进程级唯一 PersonaDistiller。"""
    global _shared_persona_distiller
    from .persona_distiller import PersonaDistiller
    if _shared_persona_distiller is None or getattr(_shared_persona_distiller, "base_dir", None) != mem_dir:
        _shared_persona_distiller = PersonaDistiller(mem_dir)
    return _shared_persona_distiller


def _reset_shared_memory(mem_dir: str) -> None:
    """隐私重置：重建共享 MemoryHub & PersonaDistiller（所有会话即时拿到干净数据）。"""
    global _shared_memory_hub, _shared_persona_distiller, _shared_mem_dir
    from .memory_hub import MemoryHub
    from .persona_distiller import PersonaDistiller
    _shared_memory_hub = MemoryHub(mem_dir)
    _shared_persona_distiller = PersonaDistiller(mem_dir)
    _shared_mem_dir = mem_dir


class ServiceContext:
    """Initializes, stores, and updates the asr, tts, and llm instances and other
    configurations for a connected client."""

    def __init__(self):
        self.config: Config = None
        self.system_config: SystemConfig = None
        self.character_config: CharacterConfig = None

        self.live2d_model: Live2dModel = None
        self.asr_engine: ASRInterface = None
        self.tts_engine: TTSInterface = None
        self.agent_engine: AgentInterface = None
        # translate_engine can be none if translation is disabled
        self.vad_engine: VADInterface | None = None
        self.translate_engine: TranslateInterface | None = None

        self.mcp_server_registery: ServerRegistry | None = None
        self.tool_adapter: ToolAdapter | None = None
        self.tool_manager: ToolManager | None = None
        self.mcp_client: MCPClient | None = None
        self.tool_executor: ToolExecutor | None = None

        # the system prompt is a combination of the persona prompt and live2d expression prompt
        self.system_prompt: str = None

        # Store the generated MCP prompt string (if MCP enabled)
        self.mcp_prompt: str = ""

        self.history_uid: str = ""  # Add history_uid field

        self.send_text: Callable = None
        self.client_uid: str = None

        # 专属记忆中枢（道/法/术/story），进程级共享单例（避免每会话旧缓存）
        from .memory_hub import MemoryHub
        self.memory_hub: MemoryHub = _get_shared_memory_hub(self._project_root_memory_dir())

        # 人格蒸馏器（融合 immortal-skill 性格四维提取机制），进程级共享单例
        from .persona_distiller import PersonaDistiller
        self.persona_distiller: PersonaDistiller = _get_shared_persona_distiller(
            self._project_root_memory_dir()
        )

    def __str__(self):
        return (
            f"ServiceContext:\n"
            f"  System Config: {'Loaded' if self.system_config else 'Not Loaded'}\n"
            f"    Details: {json.dumps(self.system_config.model_dump(), indent=6) if self.system_config else 'None'}\n"
            f"  Live2D Model: {self.live2d_model.model_info if self.live2d_model else 'Not Loaded'}\n"
            f"  ASR Engine: {type(self.asr_engine).__name__ if self.asr_engine else 'Not Loaded'}\n"
            f"    Config: {json.dumps(self.character_config.asr_config.model_dump(), indent=6) if self.character_config.asr_config else 'None'}\n"
            f"  TTS Engine: {type(self.tts_engine).__name__ if self.tts_engine else 'Not Loaded'}\n"
            f"    Config: {json.dumps(self.character_config.tts_config.model_dump(), indent=6) if self.character_config.tts_config else 'None'}\n"
            f"  LLM Engine: {type(self.agent_engine).__name__ if self.agent_engine else 'Not Loaded'}\n"
            f"    Agent Config: {json.dumps(self.character_config.agent_config.model_dump(), indent=6) if self.character_config.agent_config else 'None'}\n"
            f"  VAD Engine: {type(self.vad_engine).__name__ if self.vad_engine else 'Not Loaded'}\n"
            f"    Agent Config: {json.dumps(self.character_config.vad_config.model_dump(), indent=6) if self.character_config.vad_config else 'None'}\n"
            f"  System Prompt: {self.system_prompt or 'Not Set'}\n"
            f"  MCP Enabled: {'Yes' if self.mcp_client else 'No'}"
        )

    # ==== Initializers

    async def _init_mcp_components(self, use_mcpp, enabled_servers):
        """Initializes MCP components based on configuration, dynamically fetching tool info."""
        logger.debug(
            f"Initializing MCP components: use_mcpp={use_mcpp}, enabled_servers={enabled_servers}"
        )

        # Reset MCP components first
        self.mcp_server_registery = None
        self.tool_manager = None
        self.mcp_client = None
        self.tool_executor = None
        self.json_detector = None
        self.mcp_prompt = ""

        if use_mcpp and enabled_servers:
            # 1. Initialize ServerRegistry
            self.mcp_server_registery = ServerRegistry()
            logger.info("ServerRegistry initialized or referenced.")

            # 2. Use ToolAdapter to get the MCP prompt and tools
            if not self.tool_adapter:
                logger.error(
                    "ToolAdapter not initialized before calling _init_mcp_components."
                )
                self.mcp_prompt = "[Error: ToolAdapter not initialized]"
                return  # Exit if ToolAdapter is mandatory and not initialized

            try:
                (
                    mcp_prompt_string,
                    openai_tools,
                    claude_tools,
                ) = await self.tool_adapter.get_tools(enabled_servers)
                # Store the generated prompt string
                self.mcp_prompt = mcp_prompt_string
                logger.info(
                    f"Dynamically generated MCP prompt string (length: {len(self.mcp_prompt)})."
                )
                logger.info(
                    f"Dynamically formatted tools - OpenAI: {len(openai_tools)}, Claude: {len(claude_tools)}."
                )

                # 3. Initialize ToolManager with the fetched formatted tools

                _, raw_tools_dict = await self.tool_adapter.get_server_and_tool_info(
                    enabled_servers
                )
                self.tool_manager = ToolManager(
                    formatted_tools_openai=openai_tools,
                    formatted_tools_claude=claude_tools,
                    initial_tools_dict=raw_tools_dict,
                )
                logger.info("ToolManager initialized with dynamically fetched tools.")

            except Exception as e:
                logger.error(
                    f"Failed during dynamic MCP tool construction: {e}", exc_info=True
                )
                # Ensure dependent components are not created if construction fails
                self.tool_manager = None
                self.mcp_prompt = "[Error constructing MCP tools/prompt]"

            # 4. Initialize MCPClient
            if self.mcp_server_registery:
                self.mcp_client = MCPClient(
                    self.mcp_server_registery, self.send_text, self.client_uid
                )
                logger.info("MCPClient initialized for this session.")
            else:
                logger.error(
                    "MCP enabled but ServerRegistry not available. MCPClient not created."
                )
                self.mcp_client = None  # Ensure it's None

            # 5. Initialize ToolExecutor
            if self.mcp_client and self.tool_manager:
                self.tool_executor = ToolExecutor(self.mcp_client, self.tool_manager)
                logger.info("ToolExecutor initialized for this session.")
            else:
                logger.warning(
                    "MCPClient or ToolManager not available. ToolExecutor not created."
                )
                self.tool_executor = None  # Ensure it's None

            logger.info("StreamJSONDetector initialized for this session.")

        elif use_mcpp and not enabled_servers:
            logger.warning(
                "use_mcpp is True, but mcp_enabled_servers list is empty. MCP components not initialized."
            )
        else:
            logger.debug(
                "MCP components not initialized (use_mcpp is False or no enabled servers)."
            )

    async def close(self):
        """Clean up resources, especially the MCPClient."""
        logger.info("Closing ServiceContext resources...")
        if self.mcp_client:
            logger.info(f"Closing MCPClient for context instance {id(self)}...")
            await self.mcp_client.aclose()
            self.mcp_client = None
        if self.agent_engine and hasattr(self.agent_engine, "close"):
            await self.agent_engine.close()  # Ensure agent resources are also closed
        logger.info("ServiceContext closed.")

    async def load_cache(
        self,
        config: Config,
        system_config: SystemConfig,
        character_config: CharacterConfig,
        live2d_model: Live2dModel,
        asr_engine: ASRInterface,
        tts_engine: TTSInterface,
        vad_engine: VADInterface,
        agent_engine: AgentInterface,
        translate_engine: TranslateInterface | None,
        mcp_server_registery: ServerRegistry | None = None,
        tool_adapter: ToolAdapter | None = None,
        send_text: Callable = None,
        client_uid: str = None,
    ) -> None:
        """
        Load the ServiceContext with the reference of the provided instances.
        Pass by reference so no reinitialization will be done.
        """
        if not character_config:
            raise ValueError("character_config cannot be None")
        if not system_config:
            raise ValueError("system_config cannot be None")

        self.config = config
        self.system_config = system_config
        self.character_config = character_config
        self.live2d_model = live2d_model
        self.asr_engine = asr_engine
        self.tts_engine = tts_engine
        self.vad_engine = vad_engine
        self.agent_engine = agent_engine
        self.translate_engine = translate_engine
        # Load potentially shared components by reference
        self.mcp_server_registery = mcp_server_registery
        self.tool_adapter = tool_adapter
        self.send_text = send_text
        self.client_uid = client_uid

        # Initialize session-specific MCP components
        await self._init_mcp_components(
            self.character_config.agent_config.agent_settings.basic_memory_agent.use_mcpp,
            self.character_config.agent_config.agent_settings.basic_memory_agent.mcp_enabled_servers,
        )

        logger.debug(f"Loaded service context with cache: {character_config}")

    async def load_from_config(self, config: Config) -> None:
        """
        Load the ServiceContext with the config.
        Reinitialize the instances if the config is different.

        Parameters:
        - config (Dict): The configuration dictionary.
        """
        if not self.config:
            self.config = config

        if not self.system_config:
            self.system_config = config.system_config

        if not self.character_config:
            self.character_config = config.character_config

        # update all sub-configs

        # init live2d from character config
        self.init_live2d(config.character_config.live2d_model_name)

        # init asr from character config
        self.init_asr(config.character_config.asr_config)

        # init tts from character config
        self.init_tts(config.character_config.tts_config)

        # init vad from character config
        self.init_vad(config.character_config.vad_config)

        # Initialize shared ToolAdapter if it doesn't exist yet
        if (
            not self.tool_adapter
            and config.character_config.agent_config.agent_settings.basic_memory_agent.use_mcpp
        ):
            if not self.mcp_server_registery:
                logger.info(
                    "Initializing shared ServerRegistry within load_from_config."
                )
                self.mcp_server_registery = ServerRegistry()
            logger.info("Initializing shared ToolAdapter within load_from_config.")
            self.tool_adapter = ToolAdapter(server_registery=self.mcp_server_registery)

        # Initialize MCP Components before initializing Agent
        await self._init_mcp_components(
            config.character_config.agent_config.agent_settings.basic_memory_agent.use_mcpp,
            config.character_config.agent_config.agent_settings.basic_memory_agent.mcp_enabled_servers,
        )

        # init agent from character config
        await self.init_agent(
            config.character_config.agent_config,
            config.character_config.persona_prompt,
        )

        self.init_translate(
            config.character_config.tts_preprocessor_config.translator_config
        )

        # store typed config references
        self.config = config
        self.system_config = config.system_config or self.system_config
        self.character_config = config.character_config

    def init_live2d(self, live2d_model_name: str) -> None:
        logger.info(f"Initializing Live2D: {live2d_model_name}")
        try:
            self.live2d_model = Live2dModel(live2d_model_name)
            self.character_config.live2d_model_name = live2d_model_name
        except Exception as e:
            logger.critical(f"Error initializing Live2D: {e}")
            logger.critical("Try to proceed without Live2D...")

    def init_asr(self, asr_config: ASRConfig) -> None:
        if not self.asr_engine or (self.character_config.asr_config != asr_config):
            logger.info(f"Initializing ASR: {asr_config.asr_model}")
            try:
                self.asr_engine = ASRFactory.get_asr_system(
                    asr_config.asr_model,
                    **getattr(asr_config, asr_config.asr_model).model_dump(),
                )
            except Exception as e:
                # 非致命：ASR 失败不阻止服务启动，文本聊天/TTS/记忆照常工作；语音输入降级
                logger.warning(f"ASR 初始化失败(降级，语音输入不可用，文本聊天不受影响): {e}")
                self.asr_engine = None
            # saving config should be done after successful initialization
            self.character_config.asr_config = asr_config
        else:
            logger.info("ASR already initialized with the same config.")

    def init_tts(self, tts_config: TTSConfig) -> None:
        if not self.tts_engine or (self.character_config.tts_config != tts_config):
            logger.info(f"Initializing TTS: {tts_config.tts_model}")
            self.tts_engine = TTSFactory.get_tts_engine(
                tts_config.tts_model,
                **getattr(tts_config, tts_config.tts_model.lower()).model_dump(),
            )
            # saving config should be done after successful initialization
            self.character_config.tts_config = tts_config
        else:
            logger.info("TTS already initialized with the same config.")

    def init_vad(self, vad_config: VADConfig) -> None:
        if vad_config.vad_model is None:
            logger.info("VAD is disabled.")
            self.vad_engine = None
            return

        if not self.vad_engine or (self.character_config.vad_config != vad_config):
            logger.info(f"Initializing VAD: {vad_config.vad_model}")
            self.vad_engine = VADFactory.get_vad_engine(
                vad_config.vad_model,
                **getattr(vad_config, vad_config.vad_model.lower()).model_dump(),
            )
            # saving config should be done after successful initialization
            self.character_config.vad_config = vad_config
        else:
            logger.info("VAD already initialized with the same config.")

    async def init_agent(self, agent_config: AgentConfig, persona_prompt: str) -> None:
        """Initialize or update the LLM engine based on agent configuration."""
        logger.info(f"Initializing Agent: {agent_config.conversation_agent_choice}")

        if (
            self.agent_engine is not None
            and agent_config == self.character_config.agent_config
            and persona_prompt == self.character_config.persona_prompt
        ):
            logger.debug("Agent already initialized with the same config.")
            return

        system_prompt = await self.construct_system_prompt(persona_prompt)

        # Pass avatar to agent factory
        avatar = self.character_config.avatar or ""  # Get avatar from config

        try:
            self.agent_engine = AgentFactory.create_agent(
                conversation_agent_choice=agent_config.conversation_agent_choice,
                agent_settings=agent_config.agent_settings.model_dump(),
                llm_configs=agent_config.llm_configs.model_dump(),
                system_prompt=system_prompt,
                live2d_model=self.live2d_model,
                tts_preprocessor_config=self.character_config.tts_preprocessor_config,
                character_avatar=avatar,
                system_config=self.system_config.model_dump(),
                tool_manager=self.tool_manager,
                tool_executor=self.tool_executor,
                mcp_prompt_string=self.mcp_prompt,
            )

            logger.debug(f"Agent choice: {agent_config.conversation_agent_choice}")
            logger.debug(f"System prompt: {system_prompt}")

            # Save the current configuration
            self.character_config.agent_config = agent_config
            self.system_prompt = system_prompt

        except Exception as e:
            logger.error(f"Failed to initialize agent: {e}")
            raise

    def init_translate(self, translator_config: TranslatorConfig) -> None:
        """Initialize or update the translation engine based on the configuration."""

        if not translator_config.translate_audio:
            logger.debug("Translation is disabled.")
            return

        if (
            not self.translate_engine
            or self.character_config.tts_preprocessor_config.translator_config
            != translator_config
        ):
            logger.info(
                f"Initializing Translator: {translator_config.translate_provider}"
            )
            self.translate_engine = TranslateFactory.get_translator(
                translator_config.translate_provider,
                getattr(
                    translator_config, translator_config.translate_provider
                ).model_dump(),
            )
            self.character_config.tts_preprocessor_config.translator_config = (
                translator_config
            )
        else:
            logger.info("Translation already initialized with the same config.")

    # ==== utils

    async def construct_system_prompt(self, persona_prompt: str) -> str:
        """
        Append tool prompts to persona prompt.

        Parameters:
        - persona_prompt (str): The persona prompt.

        Returns:
        - str: The system prompt with all tool prompts appended.
        """
        logger.debug(f"constructing persona_prompt: '''{persona_prompt}'''")

        # === 当前人格设定覆盖（「一键人格」选择 MBTI 预设备后，用其替换默认人格）===
        try:
            active = self._load_active_persona()
            if active and active.get("text"):
                persona_prompt = active["text"]
                logger.info(f"使用当前自定义人格设定: {active.get('name','')}")
        except Exception as e:
            logger.debug(f"加载当前人格设定失败(非阻塞): {e}")

        for prompt_name, prompt_file in self.system_config.tool_prompts.items():
            if (
                prompt_name == "group_conversation_prompt"
                or prompt_name == "proactive_speak_prompt"
            ):
                continue

            prompt_content = prompt_loader.load_util(prompt_file)

            if prompt_name == "live2d_expression_prompt":
                prompt_content = prompt_content.replace(
                    "[<insert_emomap_keys>]", self.live2d_model.emo_str
                )

            if prompt_name == "mcp_prompt":
                continue

            persona_prompt += prompt_content

        logger.debug("\n === System Prompt ===")
        logger.debug(persona_prompt)

        # === 专属记忆知识库注入（借鉴万忆中枢「道/法/术」三层皮毛）===
        try:
            mem_dir = self._project_root_memory_dir()
            # 1) 注入静态 user_profile.md（道层摘要）
            memory_profile_path = os.path.join(mem_dir, "user_profile.md")
            if os.path.isfile(memory_profile_path):
                with open(memory_profile_path, "r", encoding="utf-8") as f:
                    profile = f.read()
                if profile.strip():
                    persona_prompt += (
                        "\n\n[附加：你对用户的专属记忆，请结合这些来更懂他]"
                        + profile
                    )
                    logger.info("已注入 user_profile.md 到 system prompt")
            else:
                logger.warning(f"记忆知识库文件不存在，跳过注入: {memory_profile_path}")

            # 2) 注入 道/法/术 三层记忆
            persona_prompt += self.memory_hub.render_for_prompt()
            logger.info("已注入 道/法/术 三层记忆到 system prompt")

            # 3) 注入人格蒸馏画像（让小青更像用户、更懂用户）
            persona_prompt += self.persona_distiller.render_for_prompt()
            logger.info("已注入人格蒸馏画像到 system prompt")
        except Exception as e:
            logger.error(f"注入记忆知识库失败: {e}")

        return persona_prompt

    async def refresh_system_prompt(self) -> str:
        """重建 system prompt，注入「最新」记忆 + 人格画像。

        产品化关键（融合 piagent / immortal-skill 的记忆中枢思路）：
        原实现只在 init_agent 时构建一次 system prompt，导致本会话新蒸馏的
        偏好/人格要重启才生效。这里提供「每轮对话前刷新」，让
        「把偏好输进去它就永远懂你」是实时的，而非启动时才生效。

        Returns:
            str: 更新后的 system prompt。
        """
        if not self.agent_engine or not self.character_config:
            return self.system_prompt or ""
        try:
            base_persona = self.character_config.persona_prompt
            new_prompt = await self.construct_system_prompt(base_persona)
            self.agent_engine.set_system(new_prompt)
            self.system_prompt = new_prompt
            # 记录记忆各层条数，便于审计
            try:
                counts = self.memory_hub.counts() if hasattr(self.memory_hub, "counts") else None
                if counts:
                    logger.info(f"已刷新系统提示（注入最新记忆 {counts}）")
                else:
                    logger.info("已刷新系统提示（注入最新记忆+人格画像）")
            except Exception:
                logger.info("已刷新系统提示（注入最新记忆+人格画像）")
            return new_prompt
        except Exception as e:
            logger.error(f"刷新系统提示失败: {e}")
            return self.system_prompt or ""

    def _project_root_memory_dir(self) -> str:
        """返回记忆目录。

        产品化：默认项目根 memory_knowledge/，但可通过环境变量 QING_MEM_DIR 指定外部文件夹，
        实现「记忆与用户文件夹相连，跨会话/跨机器持久保存」。
        """
        custom = os.getenv("QING_MEM_DIR", "").strip()
        if custom:
            os.makedirs(custom, exist_ok=True)
            logger.info(f"记忆目录使用自定义外部文件夹: {custom}")
            return custom
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        default = os.path.join(project_root, "memory_knowledge")
        os.makedirs(default, exist_ok=True)
        return default

    # === 「一键人格」/ 当前人格设定 ===
    def _active_persona_path(self) -> str:
        return os.path.join(self._project_root_memory_dir(), ".active_persona.json")

    def _load_active_persona(self) -> dict | None:
        """读取当前选中的自定义人格（MBTI 预设备等）。无则返回 None。"""
        p = self._active_persona_path()
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data and data.get("text"):
                    return data
            except Exception as e:
                logger.error(f"读取当前人格设定失败: {e}")
        return None

    def apply_persona(self, name: str) -> dict:
        """应用一个预置人格（来自 characters/*.yaml）作为当前主角色。

        找到匹配的 yaml → 提取 persona_prompt → 写入 .active_persona.json，
        并刷新 system prompt（使新人格实时生效）。

        Returns:
            dict: {name, ok} 或抛错。
        """
        # 「恢复默认」：清除当前人格设定，回到默认小青
        if name in ("默认小青（无预设）", "default", "默认小青", "__default__"):
            ap = self._active_persona_path()
            if os.path.isfile(ap):
                os.remove(ap)
            logger.info("已恢复默认人格（清除自定义设定）")
            return {"name": "默认小青", "ok": True}
        import glob
        # 到 characters/ 目录查找匹配 conf_name 的预设备
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        chars_dir = os.path.join(project_root, "characters")
        found_text = None
        found_uid = None
        for yaml_path in glob.glob(os.path.join(chars_dir, "*.yaml")):
            try:
                from .config_manager import read_yaml  # 复用 yaml 解析
                data = read_yaml(yaml_path)
            except Exception:
                continue
            cc = data.get("character_config", {}) if isinstance(data, dict) else {}
            if cc.get("conf_name") == name or cc.get("conf_uid") == name:
                found_text = cc.get("persona_prompt", "")
                found_uid = cc.get("conf_uid", "")
                break
        if not found_text:
            raise ValueError(f"未找到预置人格: {name}")
        payload = {"name": name, "uid": found_uid, "text": found_text,
                   "updated_at": datetime.now().isoformat(timespec="seconds")}
        with open(self._active_persona_path(), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        logger.info(f"已切换人格: {name}")
        return {"name": name, "ok": True}

    async def handle_config_switch(
        self,
        websocket: WebSocket,
        config_file_name: str,
    ) -> None:
        """
        Handle the configuration switch request.
        Change the configuration to a new config and notify the client.

        Parameters:
        - websocket (WebSocket): The WebSocket connection.
        - config_file_name (str): The name of the configuration file.
        """
        try:
            new_character_config_data = None

            if config_file_name == "conf.yaml":
                # Load base config
                new_character_config_data = read_yaml("conf.yaml").get(
                    "character_config"
                )
            else:
                # Load alternative config and merge with base config
                characters_dir = self.system_config.config_alts_dir
                file_path = os.path.normpath(
                    os.path.join(characters_dir, config_file_name)
                )
                if not file_path.startswith(characters_dir):
                    raise ValueError("Invalid configuration file path")

                alt_config_data = read_yaml(file_path).get("character_config")

                # Start with original config data and perform a deep merge
                new_character_config_data = deep_merge(
                    self.config.character_config.model_dump(), alt_config_data
                )

            if new_character_config_data:
                new_config = {
                    "system_config": self.system_config.model_dump(),
                    "character_config": new_character_config_data,
                }
                new_config = validate_config(new_config)
                await self.load_from_config(new_config)  # Await the async load
                logger.debug(f"New config: {self}")
                logger.debug(
                    f"New character config: {self.character_config.model_dump()}"
                )

                # Send responses to client
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "set-model-and-conf",
                            "model_info": self.live2d_model.model_info,
                            "conf_name": self.character_config.conf_name,
                            "conf_uid": self.character_config.conf_uid,
                        }
                    )
                )

                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "config-switched",
                            "message": f"Switched to config: {config_file_name}",
                        }
                    )
                )

                logger.info(f"Configuration switched to {config_file_name}")
            else:
                raise ValueError(
                    f"Failed to load configuration from {config_file_name}"
                )

        except Exception as e:
            logger.error(f"Error switching configuration: {e}")
            logger.debug(self)
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "error",
                        "message": f"Error switching configuration: {str(e)}",
                    }
                )
            )
            raise e


def deep_merge(dict1, dict2):
    """
    Recursively merges dict2 into dict1, prioritizing values from dict2.
    """
    result = dict1.copy()
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result
