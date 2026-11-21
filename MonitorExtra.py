import base64
import ipaddress
import json
import os
import socket
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time
import zipfile
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from queue import Empty, Queue
from zeroconf import IPVersion, ServiceBrowser, ServiceListener, Zeroconf
import webbrowser

DISCOVERY = "_nvstream._tcp.local."
APOLLO = "https://localhost:47990"
PREFERENCES = Path(os.environ["LOCALAPPDATA"]) / "MonitorExtra" / "connection.json"
PORTABLE = Path(os.environ["LOCALAPPDATA"]) / "TelaNaRede" / "Moonlight-6.2.0"


def package_path():
    if getattr(sys, "frozen", False):
        return Path(sys.executable)
    return Path(__file__).with_name("MonitorExtra-Automatico.exe")


def unpack_moonlight():
    with zipfile.ZipFile(package_path()) as bundle:
        with bundle.open("Moonlight-Portable.zip") as payload:
            with zipfile.ZipFile(payload) as moonlight:
                moonlight.extractall(PORTABLE)
    return str(PORTABLE / "Moonlight.exe")


def moonlight_path():
    for variable in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        folder = os.environ.get(variable)
        if not folder:
            continue
        base = Path(folder)
        for relative in ("Moonlight Game Streaming/Moonlight.exe",
                         "Programs/Moonlight Game Streaming/Moonlight.exe"):
            candidate = base / relative
            if candidate.is_file():
                return str(candidate)
    portable = PORTABLE / "Moonlight.exe"
    if portable.is_file():
        return str(portable)
    return shutil.which("Moonlight.exe")


def install_apollo():
    try:
        with zipfile.ZipFile(package_path()) as bundle:
            directory = tempfile.mkdtemp(prefix="TelaNaRede-")
            installer = bundle.extract("Apollo-Setup.exe", directory)
        os.startfile(installer)  # Windows handles the installer's elevation prompt.
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        messagebox.showerror("Instalar Apollo", str(exc))


FIREWALL_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
try {
    $original = @(Get-NetFirewallRule -DisplayName Apollo -Direction Inbound -Action Allow -ErrorAction SilentlyContinue)
    $candidates = foreach ($rule in $original) {
        ($rule | Get-NetFirewallApplicationFilter).Program
    }
    $candidates += (Join-Path $env:ProgramFiles 'Apollo\sunshine.exe')
    $apollo = $candidates | Where-Object {
        $_ -and [IO.Path]::GetFileName($_) -eq 'sunshine.exe' -and
        (Test-Path -LiteralPath ([Environment]::ExpandEnvironmentVariables($_)) -PathType Leaf)
    } | Select-Object -First 1
    if (-not $apollo) { throw 'Instale o Apollo neste computador primeiro.' }
    $apollo = [Environment]::ExpandEnvironmentVariables($apollo)
    $ports = @{ TCP = '47984','47989','48010'; UDP = '47998-48000','48002','48010' }
    foreach ($protocol in $ports.Keys) {
        $name = "TelaNaRede-Apollo-$protocol"
        $settings = @{
            Direction = 'Inbound'
            Action = 'Allow'
            Enabled = 'True'
            Profile = 'Private'
            Program = $apollo
            RemoteAddress = 'LocalSubnet'
            Protocol = $protocol
            LocalPort = $ports[$protocol]
            EdgeTraversalPolicy = 'Block'
        }
        if (Get-NetFirewallRule -Name $name -ErrorAction SilentlyContinue) {
            Set-NetFirewallRule -Name $name @settings | Out-Null
        } else {
            New-NetFirewallRule -Name $name -DisplayName "Tela na Rede - Apollo ($protocol)" @settings | Out-Null
        }
    }
    foreach ($rule in $original) {
        $program = ($rule | Get-NetFirewallApplicationFilter).Program
        if ($program -and [Environment]::ExpandEnvironmentVariables($program) -eq $apollo) {
            $rule | Disable-NetFirewallRule | Out-Null
        }
    }
    [void][Windows.Forms.MessageBox]::Show(
        'Apollo autorizado para dispositivos da rede local no perfil Privado.',
        'Tela na Rede'
    )
} catch {
    [void][Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Firewall - Tela na Rede')
    exit 1
}
"""


def authorize_firewall():
    if not messagebox.askokcancel(
        "Firewall do Windows",
        "Autorizar as portas de transmissao do Apollo somente na rede privada local? "
        "O Windows vai pedir permissao de administrador."
    ):
        return
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    encoded = base64.b64encode(FIREWALL_SCRIPT.encode("utf-16-le")).decode("ascii")
    command = (
        "try { Start-Process -FilePath (Join-Path $PSHOME 'powershell.exe') "
        "-Verb RunAs -WindowStyle Hidden -ErrorAction Stop "
        f"-ArgumentList '-NoProfile','-EncodedCommand','{encoded}' "
        "} catch { Add-Type -AssemblyName System.Windows.Forms; "
        "[void][Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Firewall - Tela na Rede') }"
    )
    try:
        subprocess.Popen(
            [str(powershell), "-NoProfile", "-Command", command],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except OSError as exc:
        messagebox.showerror("Firewall do Windows", str(exc))


def show_addresses():
    try:
        results = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
        addresses = sorted({result[4][0] for result in results if not result[4][0].startswith("127.")})
    except OSError:
        addresses = []
    if not addresses:
        messagebox.showinfo("IP deste PC", "Nenhum IPv4 encontrado. Confira a conexão de rede.")
        return
    messagebox.showinfo("IP deste PC", "No Moonlight, clique em + e digite o IP da rede local:\n\n" + "\n".join(addresses))


def receive(*arguments):
    try:
        executable = moonlight_path() or unpack_moonlight()
        subprocess.Popen([executable, *arguments], cwd=str(Path(executable).parent))
        return True
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        messagebox.showerror("Receber tela", str(exc))
        return False


def discover_hosts():
    found = {}
    local = {row[4][0] for row in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)}

    class Listener(ServiceListener):
        def add_service(self, discovery, service_type, name):
            info = discovery.get_service_info(service_type, name, timeout=800)
            if info:
                addresses = [ip for ip in info.parsed_addresses(IPVersion.V4Only) if ip not in local]
                if addresses:
                    found[name] = (name.removesuffix("." + service_type), addresses[0])

        update_service = add_service

        def remove_service(self, discovery, service_type, name):
            found.pop(name, None)

    with Zeroconf(ip_version=IPVersion.V4Only) as discovery:
        browser = ServiceBrowser(discovery, DISCOVERY, Listener())
        try:
            time.sleep(2.5)
        finally:
            browser.cancel()
    return sorted(set(found.values()))


def pair_with_ip(parent, address):
    try:
        address = str(ipaddress.IPv4Address(address.strip()))
    except ValueError:
        messagebox.showerror("Localizar por IP", "Digite um IPv4 válido, por exemplo 192.168.1.20.", parent=parent)
        return
    messagebox.showinfo(
        "Aviso de pareamento",
        "O Moonlight vai mostrar um PIN. Confirme esse PIN na aba PIN do Apollo no desktop. "
        "Depois, abra o Moonlight normalmente e escolha Virtual Display.",
        parent=parent,
    )
    receive("pair", address)



def display_mode(mode):
    executable = Path(os.environ["SystemRoot"]) / "System32" / "DisplaySwitch.exe"
    try:
        subprocess.Popen([str(executable), mode])
    except OSError as exc:
        messagebox.showerror("Modo de tela", str(exc))


def saved_address():
    try:
        data = json.loads(PREFERENCES.read_text(encoding="utf-8"))
        return str(ipaddress.IPv4Address(data["desktop"]))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def save_address(address):
    PREFERENCES.parent.mkdir(parents=True, exist_ok=True)
    temporary = PREFERENCES.with_suffix(".tmp")
    temporary.write_text(json.dumps({"desktop": address}), encoding="utf-8")
    temporary.replace(PREFERENCES)


def apollo_running():
    try:
        with socket.create_connection(("127.0.0.1", 47989), timeout=0.3):
            return (Path(os.environ["ProgramFiles"]) / "Apollo" / "sunshine.exe").is_file()
    except OSError:
        return False


def main():
    root = tk.Tk()
    root.title("Monitor Extra")
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=22)
    frame.grid()
    ttk.Label(frame, text="Monitor Extra", font=("Segoe UI", 17, "bold")).grid(sticky="w")
    ttk.Label(frame, text="Use o notebook como monitor adicional pela rede local.").grid(sticky="w", pady=(2, 12))
    tabs = ttk.Notebook(frame, width=430)
    tabs.grid(sticky="ew")

    sender = ttk.Frame(tabs, padding=14)
    tabs.add(sender, text="Desktop principal")
    ttk.Label(sender, wraplength=395, justify="left", text=(
        "No desktop, instale uma vez o Apollo com driver virtual incluído. Abra o painel. "
        "Crie o login local e confirme na aba PIN o código mostrado no outro PC.\n\n"
        "Abra o monitor extra no notebook. Depois, clique em Estender aqui."
    )).grid(sticky="w", columnspan=2, pady=(0, 12))
    ttk.Button(sender, text="Instalar Apollo", command=install_apollo).grid(row=1, column=0, sticky="w")
    ttk.Button(sender, text="Abrir painel e PIN", command=lambda: webbrowser.open(APOLLO + "/pin")).grid(row=1, column=1, sticky="w", padx=8)

    ttk.Button(sender, text="Autorizar no firewall", command=authorize_firewall).grid(row=3, column=0, sticky="w", pady=(8, 0))
    ttk.Button(sender, text="Ver IP deste PC", command=show_addresses).grid(row=3, column=1, sticky="w", padx=8, pady=(8, 0))

    ttk.Button(sender, text="Estender", command=lambda: display_mode("/extend")).grid(
        row=4, column=1, sticky="w", padx=8, pady=(8, 0)
    )

    viewer = ttk.Frame(tabs, padding=14)
    tabs.add(viewer, text="Notebook como monitor")
    ttk.Label(viewer, wraplength=395, justify="left", text=(
        "No notebook, clique em Receber tela, selecione o desktop "
        "e informe no Apollo o PIN exibido. Depois, abra Virtual Display.\n\n"
        "Se o outro PC não aparecer, use o botão + no Moonlight e digite o IPv4 dele."
    )).grid(sticky="w", columnspan=2, pady=(0, 12))
    ttk.Button(viewer, text="Receber tela", command=receive).grid(row=1, column=0, sticky="w")


    hosts = []
    results = Queue()
    status = tk.StringVar(value="Busque um desktop ou digite o IP dele.")
    host_list = ttk.Combobox(viewer, state="readonly", width=42)
    host_list.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
    ttk.Label(viewer, textvariable=status, wraplength=395).grid(
        row=2, column=0, columnspan=2, sticky="w", pady=(8, 0)
    )

    def read_discovery():
        try:
            hosts[:] = results.get_nowait()
        except Empty:
            root.after(150, read_discovery)
            return
        search_button.state(["!disabled"])
        host_list["values"] = [f"{name} ({address})" for name, address in hosts]
        if hosts:
            host_list.current(0)
            status.set(f"Computador próximo encontrado. Total: {len(hosts)}.")
            pair_button.state(["!disabled"])
        else:
            status.set("Nenhum desktop encontrado. Use Localizar por IP.")

    def search():
        def worker():
            try:
                results.put(discover_hosts())
            except OSError:
                results.put([])
        status.set("Procurando computadores na rede local…")
        search_button.state(["disabled"])
        pair_button.state(["disabled"])
        threading.Thread(target=worker, daemon=True).start()
        root.after(150, read_discovery)

    def open_monitor():
        selection = host_list.current()
        address = hosts[selection][1] if selection >= 0 else saved_address()
        if not address:
            address = simpledialog.askstring("Abrir monitor extra", "Digite o IPv4 do desktop já pareado.", parent=root)
        if not address:
            return
        try:
            address = str(ipaddress.IPv4Address(address.strip()))
        except ValueError:
            messagebox.showerror("Abrir monitor extra", "Digite um IPv4 válido.", parent=root)
            return
        if receive("stream", address, "Virtual Display"):
            if remember.get():
                try:
                    save_address(address)
                except OSError:
                    status.set("A sessão foi aberta. O Windows não permitiu salvar o endereço.")
            else:
                forget_address()

    def forget_address():
        try:
            PREFERENCES.unlink(missing_ok=True)
        except OSError:
            status.set("O Windows não permitiu apagar o endereço salvo.")

    def locate_by_ip():
        address = simpledialog.askstring("Localizar por IP", "Digite o IPv4 do desktop.", parent=root)
        if address:
            pair_with_ip(root, address)

    search_button = ttk.Button(viewer, text="Buscar próximos", command=search)
    search_button.grid(row=1, column=1, sticky="w", padx=8)
    pair_button = ttk.Button(viewer, text="Parear selecionado", command=lambda: pair_with_ip(root, hosts[host_list.current()][1]))
    pair_button.state(["disabled"])
    pair_button.grid(row=4, column=0, sticky="w", pady=(8, 0))
    ttk.Button(viewer, text="Localizar por IP", command=locate_by_ip).grid(row=4, column=1, sticky="w", padx=8, pady=(8, 0))

    ttk.Button(viewer, text="Abrir monitor extra", command=open_monitor).grid(
        row=5, column=0, sticky="w", pady=(8, 0)
    )

    remember = tk.BooleanVar(value=True)
    ttk.Checkbutton(viewer, text="Abrir automaticamente neste notebook", variable=remember,
                    command=lambda: None if remember.get() else forget_address()).grid(
        row=6, column=0, columnspan=2, sticky="w", pady=(8, 0)
    )

    def start_saved_session():
        if apollo_running():
            tabs.select(sender)
            return
        address = saved_address()
        if address:
            tabs.select(viewer)
            status.set("Abrindo o monitor extra no desktop salvo…")
            receive("stream", address, "Virtual Display")

    searched = False

    def search_on_first_visit(_event):
        nonlocal searched
        if tabs.select() == str(viewer) and not searched:
            searched = True
            if "disabled" not in search_button.state():
                search()

    tabs.bind("<<NotebookTabChanged>>", search_on_first_visit)

    if "--self-test" in sys.argv:
        root.withdraw()
        root.update_idletasks()
        assert len(tabs.tabs()) == 2
        root.destroy()
        if getattr(sys, "frozen", False):
            with zipfile.ZipFile(package_path()) as bundle:
                if bundle.testzip() is not None:
                    raise RuntimeError("Pacote interno corrompido")
                with bundle.open("Moonlight-Portable.zip") as payload:
                    with zipfile.ZipFile(payload) as moonlight:
                        assert "Moonlight.exe" in moonlight.namelist()
        return
    root.after(150, start_saved_session)
    root.mainloop()


if __name__ == "__main__":
    main()
