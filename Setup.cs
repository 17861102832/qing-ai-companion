// ============================================================
// 小青 · 安装向导 (Setup.exe)
// 编译: csc /target:winexe /out:Setup.exe /r:System.Windows.Forms.dll,System.Drawing.dll Setup.cs
// 功能: 选安装目录 -> 复制程序 -> 创建桌面/开始菜单快捷方式 -> 自动启动 -> 生成卸载
// ============================================================
using System;
using System.IO;
using System.Diagnostics;
using System.Windows.Forms;

namespace QingSetup
{
    static class Program
    {
        [STAThread]
        static void Main(string[] args)
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new SetupForm());
        }
    }

    class SetupForm : Form
    {
        private TextBox txtDir;
        private Button btnPick;
        private Button btnInstall;
        private Label lblStatus;
        private ProgressBar pbar;
        private string appName = "小青AI";
        private string defaultDir;

        public SetupForm()
        {
            defaultDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), appName);
            Text = "小青 · 安装向导";
            Width = 460; Height = 260;
            StartPosition = FormStartPosition.CenterScreen;
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false; MinimizeBox = false;

            var lbl = new Label { Text = "欢迎安装「小青」AI 数字人伴侣。", Left = 20, Top = 20, AutoSize = true, Font = new System.Drawing.Font("Microsoft YaHei", 10, System.Drawing.FontStyle.Bold) };

            var lblDir = new Label { Text = "安装目录:", Left = 20, Top = 60, AutoSize = true };
            txtDir = new TextBox { Left = 100, Top = 56, Width = 260, Text = defaultDir };
            btnPick = new Button { Text = "浏览…", Left = 366, Top = 54, Width = 70 };
            btnPick.Click += delegate { using (var fbd = new FolderBrowserDialog()) { fbd.SelectedPath = txtDir.Text; if (fbd.ShowDialog() == DialogResult.OK) txtDir.Text = fbd.SelectedPath; } };

            btnInstall = new Button { Text = "开始安装", Left = 260, Top = 150, Width = 90, Height = 34 };
            btnInstall.Click += delegate { Install(); };

            pbar = new ProgressBar { Left = 20, Top = 112, Width = 396, Height = 20, Minimum = 0, Maximum = 100 };
            lblStatus = new Label { Text = "准备就绪", Left = 20, Top = 138, AutoSize = true };

            var btnCancel = new Button { Text = "退出", Left = 358, Top = 150, Width = 58 };
            btnCancel.Click += delegate { Application.Exit(); };

            Controls.Add(lbl); Controls.Add(lblDir); Controls.Add(txtDir);
            Controls.Add(btnPick); Controls.Add(btnInstall);
            Controls.Add(pbar); Controls.Add(lblStatus); Controls.Add(btnCancel);
        }

        private void Install()
        {
            string src = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "app");
            string dst = txtDir.Text;
            try
            {
                btnInstall.Enabled = false;
                lblStatus.Text = "正在复制文件…";
                pbar.Value = 10;
                Application.DoEvents();

                if (!Directory.Exists(src))
                {
                    MessageBox.Show("未找到程序源目录 app\\，请将 Setup.exe 与 app 文件夹放在一起。", "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    btnInstall.Enabled = true; return;
                }

                if (Directory.Exists(dst)) TryDelete(dst);
                Directory.CreateDirectory(dst);
                CopyDir(src, dst);
                pbar.Value = 55;

                // 用 PowerShell 生成快捷方式（桌面 + 开始菜单）
                lblStatus.Text = "正在创建快捷方式…";
                Application.DoEvents();
                CreateShortcut(dst);
                pbar.Value = 80;

                // 生成卸载批处理
                File.WriteAllText(Path.Combine(dst, "卸载小青.bat"),
                    "@echo off\necho 正在卸载小青...\nrd /s /q \"" + dst + "\"\ndel \"%~f0\"\n");

                // 自动写入默认 .env 模板（若缺）
                string env = Path.Combine(dst, ".env");
                if (!File.Exists(env)) File.WriteAllText(env, "DEEPSEEK_API_KEY=sk-please-fill-me\n#QING_MEM_DIR=\n");

                pbar.Value = 90;
                lblStatus.Text = "安装完成，正在启动…";
                Application.DoEvents();

                // 启动程序
                string exe = Path.Combine(dst, "小青.exe");
                if (File.Exists(exe)) Process.Start(exe);
                pbar.Value = 100;

                MessageBox.Show("安装成功！小青将自动启动。\n已创建桌面和开始菜单快捷方式。\n\n首次使用请在界面的「一键蒸馏·人格」面板填写你的 DeepSeek Key。",
                    "完成", MessageBoxButtons.OK, MessageBoxIcon.Information);
                Application.Exit();
            }
            catch (Exception ex)
            {
                MessageBox.Show("安装失败: " + ex.Message, "错误", MessageBoxButtons.OK, MessageBoxIcon.Error);
                btnInstall.Enabled = true;
            }
        }

        private static void CreateShortcut(string dst)
        {
            string desktop = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
            string startmenu = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.StartMenu), "程序");
            string exe = Path.Combine(dst, "小青.exe");
            if (!File.Exists(exe)) return;

            // 用 WScript.Shell COM 建 .lnk
            dynamic shell = Activator.CreateInstance(Type.GetTypeFromProgID("WScript.Shell"));
            MakeLnk(shell, Path.Combine(desktop, "小青.lnk"), exe, dst);
            MakeLnk(shell, Path.Combine(startmenu, "小青.lnk"), exe, dst);
        }

        private static void MakeLnk(dynamic shell, string lnkPath, string target, string workdir)
        {
            try
            {
                dynamic shortcut = shell.CreateShortcut(lnkPath);
                shortcut.TargetPath = target;
                shortcut.WorkingDirectory = workdir;
                shortcut.Description = "小青 AI 数字人伴侣";
                shortcut.Save();
            }
            catch { }
        }

        private static void CopyDir(string src, string dst)
        {
            foreach (string dir in Directory.GetDirectories(src, "*", SearchOption.AllDirectories))
                Directory.CreateDirectory(dir.Replace(src, dst));
            foreach (string file in Directory.GetFiles(src, "*", SearchOption.AllDirectories))
                File.Copy(file, file.Replace(src, dst), true);
        }

        private static void TryDelete(string path)
        {
            try { Directory.Delete(path, true); } catch { }
        }
    }
}
