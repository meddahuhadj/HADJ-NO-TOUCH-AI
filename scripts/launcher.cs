using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

namespace HadjLauncher
{
    class Program
    {
        [STAThread]
        static int Main(string[] args)
        {
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string py = Path.Combine(baseDir, "runtime", "pythonw.exe");
            string mainPy = Path.Combine(baseDir, "app", "main.py");

            if (!File.Exists(py))
            {
                py = Path.Combine(baseDir, "runtime", "python.exe");
            }

            if (!File.Exists(py) || !File.Exists(mainPy))
            {
                MessageBox.Show(
                    "Fichiers nécessaires introuvables.\nVeuillez vous assurer que les dossiers 'runtime' et 'app' sont bien extraits.",
                    "HADJ NO-TOUCH AI",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
                return 1;
            }

            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = py;
            psi.Arguments = "-s -E \"" + mainPy + "\" " + string.Join(" ", args);
            psi.WorkingDirectory = baseDir;
            psi.UseShellExecute = false;
            psi.CreateNoWindow = true;

            try
            {
                Process.Start(psi);
                return 0;
            }
            catch (Exception ex)
            {
                MessageBox.Show(
                    "Erreur lors du lancement : " + ex.Message,
                    "HADJ NO-TOUCH AI",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
                return 1;
            }
        }
    }
}
