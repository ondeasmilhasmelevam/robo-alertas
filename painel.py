#!/usr/bin/env python3
"""Onde As Milhas Me Levam - Painel v7 - Clean Professional"""
import customtkinter as ctk
from tkinter import ttk, messagebox
import threading, time, logging, os, sys
from datetime import datetime
from channels import load_config, save_config, AVAILABLE_REGIONS, AVAILABLE_CABINS
from seats_api import SeatsAeroClient
from telegram_bot import TelegramBot
from engine import run_cycle_for_channel, run_melhores_destinos, run_iberia_scan, run_weekly_summary

logger = logging.getLogger("miles_bot")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

PROGRAMS = [("azul","Azul (TudoAzul)"),("smiles","GOL (Smiles)"),("latam","LATAM Pass"),("aeroplan","Aeroplan"),("american","American (AAdvantage)"),("delta","Delta (SkyMiles)"),("united","United (MileagePlus)"),("emirates","Emirates (Skywards)"),("turkish","Turkish (Miles&Smiles)"),("qatar","Qatar (Privilege Club)"),("singapore","Singapore (KrisFlyer)"),("flyingblue","Flying Blue"),("lufthansa","Lufthansa"),("virginatlantic","Virgin Atlantic"),("copa","Copa (ConnectMiles)"),("alaska","Alaska (Atmos)"),("qantas","Qantas"),("etihad","Etihad (Guest)"),("finnair","Finnair"),("iberia","Iberia (Avios)"),("british","British Airways"),("tap","TAP (Miles&Go)"),("jetblue","JetBlue")]

def rp(f):
    if hasattr(sys,'_MEIPASS'):return os.path.join(sys._MEIPASS,f)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),f)

# Cores do tema
C_GREEN = "#22c55e"
C_GREEN_DARK = "#16a34a"
C_GREEN_LIGHT = "#86efac"
C_RED = "#ef4444"

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Onde As Milhas Me Levam")
        self.geometry("1180x850")
        self.minsize(960,720)
        try:self.iconbitmap(rp("logo.ico"))
        except:pass
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")
        self.cd = load_config()
        self.running = False
        self.thread = None
        self._build()
        self._style_tree()
        self._load_list()

    def _build(self):
        # Header
        hd = ctk.CTkFrame(self, height=56, corner_radius=0, fg_color=("#fafafa","#161b22"))
        hd.pack(fill="x"); hd.pack_propagate(False)
        try:
            from PIL import Image
            lp = rp("logo_small.png")
            if os.path.exists(lp):
                img = ctk.CTkImage(light_image=Image.open(lp), dark_image=Image.open(lp), size=(38,38))
                ctk.CTkLabel(hd, image=img, text="").pack(side="left", padx=(20,10))
        except: pass
        ctk.CTkLabel(hd, text="Onde As Milhas Me Levam", font=ctk.CTkFont(family="Georgia",size=18,weight="bold"), text_color=("#16a34a",C_GREEN)).pack(side="left")
        ctk.CTkLabel(hd, text="Painel de Controle", font=ctk.CTkFont(size=11), text_color=("#999","#666")).pack(side="left", padx=(10,0))
        # Right side header
        self.status_pill = ctk.CTkLabel(hd, text="  Offline  ", font=ctk.CTkFont(size=10), text_color="#fff", fg_color=("#ccc","#333"), corner_radius=10, height=24)
        self.status_pill.pack(side="right", padx=20)
        self.theme_btn = ctk.CTkButton(hd, text="Tema", width=60, height=28, font=ctk.CTkFont(size=10), fg_color="transparent", border_width=1, border_color=("#ddd","#333"), text_color=("#666","#888"), hover_color=("#eee","#222"), command=self._tt)
        self.theme_btn.pack(side="right", padx=5)
        ctk.CTkFrame(self, height=2, corner_radius=0, fg_color=C_GREEN).pack(fill="x")

        # Main
        self.main = ctk.CTkScrollableFrame(self, fg_color=("#f0f2f5","#0d1117"))
        self.main.pack(fill="both", expand=True)

        # Credenciais
        self._card_cred()
        # Canais
        self._card_channels()
        # Controles
        self._card_controls()
        # Log
        self._card_log()

    def _card(self, parent, title):
        f = ctk.CTkFrame(parent, corner_radius=8, fg_color=("#fff","#161b22"), border_width=1, border_color=("#e5e7eb","#21262d"))
        f.pack(fill="x", padx=20, pady=6)
        if title:
            ctk.CTkLabel(f, text=title, font=ctk.CTkFont(size=12, weight="bold"), text_color=("#16a34a",C_GREEN)).pack(anchor="w", padx=16, pady=(12,6))
        return f

    def _card_cred(self):
        c = self._card(self.main, "Credenciais")
        for lbl, attr, key in [("API Key seats.aero","api_var","seats_api_key"),("Token Bot Telegram","tok_var","telegram_bot_token")]:
            r = ctk.CTkFrame(c, fg_color="transparent"); r.pack(fill="x", padx=16, pady=2)
            ctk.CTkLabel(r, text=lbl, font=ctk.CTkFont(size=11), width=160, anchor="w").pack(side="left")
            v = ctk.StringVar(value=self.cd.get(key,"")); setattr(self, attr, v)
            ctk.CTkEntry(r, textvariable=v, show="*", width=500, height=32, font=ctk.CTkFont(family="Consolas",size=10), corner_radius=6).pack(side="left", padx=5)

        r = ctk.CTkFrame(c, fg_color="transparent"); r.pack(fill="x", padx=16, pady=(2,12))
        ctk.CTkLabel(r, text="Intervalo (min)", font=ctk.CTkFont(size=11), width=160, anchor="w").pack(side="left")
        self.int_var = ctk.StringVar(value=str(self.cd.get("check_interval_minutes",60)))
        ctk.CTkEntry(r, textvariable=self.int_var, width=55, height=32, corner_radius=6).pack(side="left", padx=5)
        ctk.CTkLabel(r, text="Max alertas/ciclo", font=ctk.CTkFont(size=11)).pack(side="left", padx=(20,0))
        self.max_var = ctk.StringVar(value=str(self.cd.get("max_alerts_per_cycle",10)))
        ctk.CTkEntry(r, textvariable=self.max_var, width=50, height=32, corner_radius=6).pack(side="left", padx=5)

        rr = ctk.CTkFrame(c, fg_color="transparent"); rr.pack(fill="x", padx=16, pady=(0,12))
        self.rove_var = ctk.BooleanVar(value=self.cd.get("rove_enabled", False))
        ctk.CTkCheckBox(rr, text="Incluir preço pago (Rove)", variable=self.rove_var,
            font=ctk.CTkFont(size=11), height=26, checkbox_width=18, checkbox_height=18,
            corner_radius=4, command=self._toggle_rove).pack(side="left")
        ctk.CTkLabel(rr, text="(preencha as credenciais Rove no channels_config.json)",
            font=ctk.CTkFont(size=10), text_color=("#999","#666")).pack(side="left", padx=(10,0))

        ra = ctk.CTkFrame(c, fg_color="transparent"); ra.pack(fill="x", padx=16, pady=(0,12))
        self.avios_var = ctk.BooleanVar(value=self.cd.get("avios_enabled", False))
        ctk.CTkCheckBox(ra, text="Incluir Avios oficial (Iberia/British)", variable=self.avios_var,
            font=ctk.CTkFont(size=11), height=26, checkbox_width=18, checkbox_height=18,
            corner_radius=4, command=self._toggle_avios).pack(side="left")
        ctk.CTkButton(ra, text="Conectar conta Avios", width=150, height=26,
            font=ctk.CTkFont(size=10), corner_radius=6,
            command=self._avios_login).pack(side="left", padx=(12,4))
        ctk.CTkButton(ra, text="Verificar", width=80, height=26,
            font=ctk.CTkFont(size=10), corner_radius=6, fg_color="transparent",
            border_width=1, border_color=("#ddd","#333"), text_color=("#666","#888"),
            hover_color=("#eee","#222"),
            command=self._avios_check).pack(side="left", padx=2)
        self.avios_scan_btn = ctk.CTkButton(ra, text="Varrer agora", width=100, height=26,
            font=ctk.CTkFont(size=10), corner_radius=6,
            fg_color=C_GREEN_DARK, hover_color=C_GREEN,
            command=self._avios_scan_now)
        self.avios_scan_btn.pack(side="left", padx=(6,2))
        self.avios_show_var = ctk.BooleanVar(
            value=(self.cd.get("avios_browser_mode", "minimizado") == "visivel"))
        ctk.CTkCheckBox(ra, text="Mostrar navegador", variable=self.avios_show_var,
            font=ctk.CTkFont(size=10), height=24, checkbox_width=16, checkbox_height=16,
            corner_radius=4, command=self._toggle_avios_show).pack(side="left", padx=(10,0))
        self.avios_status = ctk.CTkLabel(ra, text="  ● Avios: não verificado  ",
            font=ctk.CTkFont(size=10, weight="bold"), text_color=("#999","#666"))
        self.avios_status.pack(side="left", padx=(10,0))
        ctk.CTkLabel(ra, text="(varre nas aberturas 0h/6h/21h)",
            font=ctk.CTkFont(size=10), text_color=("#999","#666")).pack(side="left", padx=(8,0))
        try:
            import avios_api
            avios_api.set_status_callback(self._avios_status_cb)
        except Exception:
            pass

    def _avios_scan_now(self):
        """Força uma varredura Avios na hora (fora dos horários 0h/6h/21h)."""
        if getattr(self, "_avios_scanning", False):
            self._wl("Avios: já tem uma varredura rodando — aguarde.")
            return
        self._avios_scanning = True
        try:
            self.avios_scan_btn.configure(state="disabled", text="Varrendo...")
        except Exception:
            pass
        self._wl("Avios: varredura MANUAL iniciada (pode levar alguns minutos)...")

        def run():
            try:
                import avios_runner
                enviados = avios_runner.run_once(self.cd, log=self._ts, send=True)
                self._ts(f"[Avios] varredura manual concluída — {len(enviados)} alerta(s).")
            except Exception as e:
                self._ts(f"[Avios] erro na varredura manual: {e}")
            finally:
                self._avios_scanning = False
                try:
                    self.after(0, lambda: self.avios_scan_btn.configure(
                        state="normal", text="Varrer agora"))
                except Exception:
                    pass
        threading.Thread(target=run, daemon=True).start()

    def _toggle_avios_show(self):
        """Mostrar navegador durante a varredura (ligado) ou rodar fora da tela."""
        modo = "visivel" if self.avios_show_var.get() else "minimizado"
        self.cd["avios_browser_mode"] = modo
        try: save_config(self.cd)
        except Exception: pass
        self._wl("Avios — navegador: " + ("VISÍVEL" if modo == "visivel"
                                          else "minimizado"))

    def _avios_status_cb(self, connected, detail=""):
        """Recebe o estado da conexão Avios (de qualquer thread) e pinta o sinalizador."""
        if connected:
            txt = "  ● Avios: CONECTADO  " + (f"({detail})" if detail else "")
            cor = C_GREEN
        else:
            txt = "  ● Avios: DESCONECTADO  " + (f"({detail})" if detail else "")
            cor = C_RED
        try:
            self.after(0, lambda: self.avios_status.configure(text=txt, text_color=cor))
        except Exception:
            pass

    def _avios_login(self):
        """Abre o navegador pro usuário logar na Avios (sem terminal)."""
        def run():
            try:
                import avios_api
                avios_api.open_login_window(self._ts)
                avios_api.watch_login(self._ts)   # acende o sinal sozinho ao logar
            except Exception as e:
                self._ts(f"[Avios] não consegui abrir o navegador: {e}")
        threading.Thread(target=run, daemon=True).start()

    def _avios_check(self):
        """Verifica se a sessão da Avios ainda está válida."""
        self._wl("Avios: verificando conexão...")
        def run():
            try:
                import avios_api
                avios_api.check_login(self._ts)
            except Exception as e:
                self._ts(f"[Avios] falha ao verificar: {e}")
        threading.Thread(target=run, daemon=True).start()

    def _toggle_rove(self):
        self.cd["rove_enabled"] = bool(self.rove_var.get())
        try: save_config(self.cd)
        except Exception: pass
        self._wl("Rove (preço pago): " + ("LIGADO" if self.cd["rove_enabled"] else "desligado"))

    def _toggle_avios(self):
        self.cd["avios_enabled"] = bool(self.avios_var.get())
        try: save_config(self.cd)
        except Exception: pass
        self._wl("Avios oficial (Iberia/British): " + ("LIGADO" if self.cd["avios_enabled"] else "desligado"))

    def _card_channels(self):
        c = self._card(self.main, "Canais")
        tf = ctk.CTkFrame(c, fg_color="transparent"); tf.pack(fill="x", padx=16, pady=4)
        cols = ("name","origins","regions","cabins","programs","md","status")
        self.tree = ttk.Treeview(tf, columns=cols, show="headings", height=5, style="T.Treeview")
        for col,h,w in [("name","Canal",170),("origins","Origens",90),("regions","Regioes",130),("cabins","Cabines",100),("programs","Programas",140),("md","MD",35),("status","",50)]:
            self.tree.heading(col, text=h); self.tree.column(col, width=w, anchor="w" if col != "md" else "center")
        self.tree.pack(fill="x")

        bf = ctk.CTkFrame(c, fg_color="transparent"); bf.pack(fill="x", padx=16, pady=(6,12))
        for txt, cmd in [("Adicionar",self._add),("Editar",self._edit),("Remover",self._rm),("Testar",self._test)]:
            ctk.CTkButton(bf, text=txt, width=100, height=30, font=ctk.CTkFont(size=11), corner_radius=6,
                fg_color=("#f3f4f6","#1c2128"), border_width=1, border_color=("#ddd","#30363d"),
                text_color=("#333","#ccc"), hover_color=("#e5e7eb","#262c34"), command=cmd).pack(side="left", padx=3)

    def _card_controls(self):
        cf = ctk.CTkFrame(self.main, fg_color="transparent"); cf.pack(fill="x", padx=20, pady=8)
        self.go_btn = ctk.CTkButton(cf, text="Iniciar Monitoramento", width=220, height=42,
            font=ctk.CTkFont(size=13, weight="bold"), corner_radius=8,
            fg_color=C_GREEN_DARK, hover_color=C_GREEN, command=self._start)
        self.go_btn.pack(side="left", padx=4)
        self.sp_btn = ctk.CTkButton(cf, text="Parar", width=100, height=42,
            font=ctk.CTkFont(size=13, weight="bold"), corner_radius=8,
            fg_color=C_RED, hover_color="#dc2626", state="disabled", command=self._stop)
        self.sp_btn.pack(side="left", padx=4)
        self.auto_lbl = ctk.CTkLabel(cf, text="", font=ctk.CTkFont(size=11, weight="bold"))
        self.auto_lbl.pack(side="left", padx=12)
        ctk.CTkButton(cf, text="Salvar", width=90, height=38, font=ctk.CTkFont(size=11), corner_radius=6,
            fg_color=("#f3f4f6","#1c2128"), border_width=1, border_color=("#ddd","#30363d"),
            text_color=("#333","#ccc"), hover_color=("#e5e7eb","#262c34"), command=self._save).pack(side="right", padx=4)

    def _card_log(self):
        c = self._card(self.main, "Log")
        self.log_box = ctk.CTkTextbox(c, height=200, font=ctk.CTkFont(family="Consolas",size=10),
            fg_color=("#f8f9fa","#0d1117"), text_color=("#16a34a",C_GREEN), corner_radius=6)
        self.log_box.pack(fill="both", expand=True, padx=12, pady=(0,12))
        self.log_box.configure(state="disabled")

    def _style_tree(self):
        s = ttk.Style(); s.theme_use("clam")
        m = ctk.get_appearance_mode()
        if m == "Dark":
            s.configure("T.Treeview", background="#161b22", foreground="#e6edf3", fieldbackground="#161b22", font=("Segoe UI",10), rowheight=28, borderwidth=0)
            s.configure("T.Treeview.Heading", background="#1c2128", foreground=C_GREEN, font=("Segoe UI",10,"bold"), borderwidth=0, relief="flat")
            s.map("T.Treeview", background=[("selected",C_GREEN_DARK)], foreground=[("selected","white")])
        else:
            s.configure("T.Treeview", background="#fff", foreground="#1f2937", fieldbackground="#fff", font=("Segoe UI",10), rowheight=28, borderwidth=0)
            s.configure("T.Treeview.Heading", background="#f9fafb", foreground="#16a34a", font=("Segoe UI",10,"bold"), borderwidth=0, relief="flat")
            s.map("T.Treeview", background=[("selected","#16a34a")], foreground=[("selected","white")])

    def _tt(self):
        if ctk.get_appearance_mode()=="Dark": ctk.set_appearance_mode("light")
        else: ctk.set_appearance_mode("dark")
        self.after(100, self._style_tree)

    def _load_list(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        chs = self.cd.get("channels",[])
        for c in chs:
            rn = [n for k,n in AVAILABLE_REGIONS if k in c.get("regions",[])]
            cn = [n for k,n in AVAILABLE_CABINS if k in c.get("cabins",[])]
            pn = [n for k,n in PROGRAMS if k in c.get("programs",[])]
            pd = f"{len(pn)} prog." if pn else "Todos"
            ori = ", ".join(c.get("origins",["GIG","GRU"]))
            md = "Sim" if c.get("melhores_destinos",False) else "-"
            st = "On" if c.get("enabled",True) else "Off"
            self.tree.insert("","end",values=(c["name"],ori,", ".join(rn),", ".join(cn),pd,md,st))
        n = len([c for c in chs if c.get("enabled",True)])
        self.status_pill.configure(text=f"  {n} canal(is)  ")

    def _add(self): ChannelDialog(self,"Novo Canal",cb=self._svd)
    def _edit(self):
        s=self.tree.selection()
        if not s:messagebox.showwarning("Aviso","Selecione um canal.");return
        ChannelDialog(self,"Editar Canal",ch=self.cd["channels"][self.tree.index(s[0])],idx=self.tree.index(s[0]),cb=self._svd)
    def _rm(self):
        s=self.tree.selection()
        if not s:return
        i=self.tree.index(s[0])
        if messagebox.askyesno("Confirmar",f"Remover '{self.cd['channels'][i]['name']}'?"):self.cd["channels"].pop(i);save_config(self.cd);self._load_list()
    def _test(self):
        s=self.tree.selection()
        if not s:return
        c=self.cd["channels"][self.tree.index(s[0])];tok=self.tok_var.get().strip()
        if not tok:messagebox.showerror("Erro","Token.");return
        from telegram_bot import TelegramBot as TB
        b=TB(tok,c["chat_id"])
        if b.test_connection():messagebox.showinfo("OK",f"Enviado para '{c['name']}'!")
        else:messagebox.showerror("Erro","Falha. Verifique Chat ID.")
    def _svd(self,data,idx=None):
        if idx is not None:self.cd["channels"][idx]=data
        else:self.cd["channels"].append(data)
        save_config(self.cd);self._load_list()
    def _save(self):
        self.cd["seats_api_key"]=self.api_var.get().strip()
        self.cd["telegram_bot_token"]=self.tok_var.get().strip()
        self.cd["check_interval_minutes"]=int(self.int_var.get() or 60)
        self.cd["max_alerts_per_cycle"]=int(self.max_var.get() or 10)
        save_config(self.cd);self._wl("Configuracao salva!")
    def _start(self):
        self._save();ak=self.cd.get("seats_api_key","");tok=self.cd.get("telegram_bot_token","")
        chs=[c for c in self.cd.get("channels",[]) if c.get("enabled",True)]
        if not ak or "SUA_API" in ak:messagebox.showerror("Erro","API Key.");return
        if not tok or "SEU_TOKEN" in tok:messagebox.showerror("Erro","Token.");return
        if not chs:messagebox.showerror("Erro","Adicione um canal.");return
        self.running=True;self.go_btn.configure(state="disabled");self.sp_btn.configure(state="normal")
        self.auto_lbl.configure(text="Monitorando...",text_color=C_GREEN)
        self.status_pill.configure(text="  Online  ",fg_color=C_GREEN_DARK)
        self._wl("Monitoramento iniciado!")
        self._wl("Varredura Iberia/British/Qatar agendada: 21:02 e 21:05")
        self._wl("Resumo semanal agendado: sexta-feira 20:00")
        self._wl("Userbot VMM (repost) iniciando junto...")
        self.thread=threading.Thread(target=self._loop,daemon=True);self.thread.start()
        self.iberia_thread=threading.Thread(target=self._iberia_scheduler,daemon=True);self.iberia_thread.start()
        self.vmm_thread=threading.Thread(target=self._start_vmm_userbot,daemon=True);self.vmm_thread.start()
        if self.cd.get("rove_enabled"):
            self._wl("Rove (preço pago) ligado — testando conexão...")
            self.rove_thread=threading.Thread(target=self._start_rove,daemon=True);self.rove_thread.start()
        if self.cd.get("avios_enabled"):
            self._wl("Avios oficial ligado — varredura agendada (0h/6h/21h).")
            self.avios_thread=threading.Thread(target=self._start_avios,daemon=True);self.avios_thread.start()
    def _stop(self):
        self.running=False;self.go_btn.configure(state="normal");self.sp_btn.configure(state="disabled")
        self.auto_lbl.configure(text="Parado",text_color=C_RED)
        self.status_pill.configure(text="  Offline  ",fg_color=("#ccc","#333"))
        self._wl("Parado.")
    def _start_vmm_userbot(self):
        """Roda o userbot de repost do VMM na mesma aplicação (thread daemon)."""
        try:
            import repost_vmm
            repost_vmm.start_background(self._ts)
        except Exception as e:
            self._ts(f"[VMM] Userbot não iniciado: {e}")
    def _start_rove(self):
        """Testa a conexão com o Rove e reporta os preços no log."""
        try:
            import rove_api
            rove_api.start_test(self._ts)
        except Exception as e:
            self._ts(f"[Rove] não iniciou: {e}")
    def _start_avios(self):
        """Sobe a varredura Avios.com em segundo plano (roda nas aberturas 0h/6h/21h)."""
        try:
            import avios_runner
            avios_runner.start_background(lambda: self.cd, self._ts)
        except Exception as e:
            self._ts(f"[Avios] não iniciou: {e}")
    def _loop(self):
        cl=SeatsAeroClient(self.cd["seats_api_key"]);bt=TelegramBot(self.cd["telegram_bot_token"],"")
        iv=self.cd["check_interval_minutes"];mx=self.cd["max_alerts_per_cycle"]
        while self.running:
            chs=[c for c in self.cd.get("channels",[]) if c.get("enabled",True)]
            self._ts(f"\n{'='*50}");self._ts(f"Ciclo - {datetime.now().strftime('%d/%m/%Y %H:%M')}")
            for c in chs:
                if not self.running:break
                ori=c.get("origins",["GIG","GRU"])
                try:run_cycle_for_channel(client=cl,bot=bt,channel=c,origins=ori,max_alerts=mx,callback=self._ts)
                except Exception as e:self._ts(f"[{c['name']}] Erro: {e}")
            if self.running:
                try:run_melhores_destinos(bt,chs,callback=self._ts)
                except:pass
            if not self.running:break
            self._ts(f"Proximo ciclo em {iv} min...")
            for _ in range(iv*60):
                if not self.running:break
                time.sleep(1)

    def _iberia_scheduler(self):
        """Thread que monitora o horário e dispara varreduras Iberia às 21:02 e 21:05."""
        SCAN_TIMES = [(21, 2), (21, 5)]  # (hora, minuto)
        already_ran = set()  # Evita rodar mais de uma vez no mesmo minuto

        cl = SeatsAeroClient(self.cd["seats_api_key"])
        bt = TelegramBot(self.cd["telegram_bot_token"], "")
        mx = self.cd["max_alerts_per_cycle"]

        while self.running:
            now = datetime.now()
            current = (now.hour, now.minute)
            today = now.strftime("%Y-%m-%d")
            key = f"{today}_{current[0]}:{current[1]}"

            if current in SCAN_TIMES and key not in already_ran:
                already_ran.add(key)
                chs = [c for c in self.cd.get("channels", []) if c.get("enabled", True)]
                ori_set = set()
                for c in chs:
                    for o in c.get("origins", ["GIG", "GRU"]):
                        ori_set.add(o)
                origins = list(ori_set)

                try:
                    run_iberia_scan(
                        client=cl, bot=bt, channels=chs,
                        origins=origins, max_alerts=mx,
                        callback=self._ts
                    )
                except Exception as e:
                    self._ts(f"[Iberia Scan] Erro: {e}")

            # Resumo semanal: toda SEXTA-FEIRA às 20:00
            WEEKLY_TIME = (20, 0)
            if now.weekday() == 4 and current == WEEKLY_TIME and (key + "_wk") not in already_ran:
                already_ran.add(key + "_wk")
                chs = [c for c in self.cd.get("channels", []) if c.get("enabled", True)]
                try:
                    run_weekly_summary(bt, chs, callback=self._ts)
                except Exception as e:
                    self._ts(f"[Resumo Semanal] Erro: {e}")

            # Limpar registros de dias anteriores
            old_keys = [k for k in already_ran if not k.startswith(today)]
            for k in old_keys:
                already_ran.discard(k)

            time.sleep(10)  # Checa a cada 10 segundos
    def _wl(self,m):
        ts=datetime.now().strftime("%H:%M:%S");self.log_box.configure(state="normal")
        self.log_box.insert("end",f"{ts}  {m}\n");self.log_box.see("end");self.log_box.configure(state="disabled")
    def _ts(self,m):self.after(0,self._wl,m)


class ChannelDialog(ctk.CTkToplevel):
    def __init__(self,parent,title,ch=None,idx=None,cb=None):
        super().__init__(parent);self.title(title);self.geometry("660x800");self.resizable(False,False)
        self.transient(parent);self.grab_set();self.cb=cb;self.idx=idx;self.ch=ch or {}
        try:self.iconbitmap(rp("logo.ico"))
        except:pass
        self.after(100,self._build)

    def _build(self):
        m=ctk.CTkScrollableFrame(self,fg_color="transparent");m.pack(fill="both",expand=True,padx=12,pady=12)
        TF=ctk.CTkFont(size=12,weight="bold");SF=ctk.CTkFont(size=11);GC=("#16a34a",C_GREEN)

        def section(text):
            ctk.CTkLabel(m,text=text,font=TF,text_color=GC).pack(anchor="w",padx=12,pady=(12,3))

        section("Nome do Grupo")
        self.nv=ctk.StringVar(value=self.ch.get("name",""))
        ctk.CTkEntry(m,textvariable=self.nv,width=520,height=34,corner_radius=6).pack(anchor="w",padx=12)

        section("Chat ID")
        self.cv=ctk.StringVar(value=self.ch.get("chat_id",""))
        ctk.CTkEntry(m,textvariable=self.cv,width=520,height=34,corner_radius=6).pack(anchor="w",padx=12)

        section("Origens (IATA)")
        rf=ctk.CTkFrame(m,fg_color="transparent");rf.pack(anchor="w",padx=12)
        self.ori_var=ctk.StringVar(value=", ".join(self.ch.get("origins",["GIG","GRU"])))
        ctk.CTkEntry(rf,textvariable=self.ori_var,width=300,height=34,corner_radius=6,placeholder_text="GIG, GRU, FOR").pack(side="left")
        ctk.CTkLabel(rf,text="ex: GIG, GRU, FOR",font=ctk.CTkFont(size=10),text_color="#888").pack(side="left",padx=8)

        section("Destinos Avios (IATA)")
        df=ctk.CTkFrame(m,fg_color="transparent");df.pack(anchor="w",padx=12)
        self.avidest_var=ctk.StringVar(value=", ".join(self.ch.get("avios_destinations",[])))
        ctk.CTkEntry(df,textvariable=self.avidest_var,width=300,height=34,corner_radius=6,
                     placeholder_text="MAD, LHR, BCN").pack(side="left")
        ctk.CTkLabel(df,text="varredura Avios: origens x estes destinos (vazio = não varre)",
                     font=ctk.CTkFont(size=10),text_color="#888").pack(side="left",padx=8)

        section("Regioes")
        rgf=ctk.CTkFrame(m,fg_color="transparent");rgf.pack(anchor="w",padx=12)
        self.rv={};cr=self.ch.get("regions",[])
        for i,(c,n) in enumerate(AVAILABLE_REGIONS):
            v=ctk.BooleanVar(value=c in cr);self.rv[c]=v
            ctk.CTkCheckBox(rgf,text=n,variable=v,font=SF,height=26,checkbox_width=18,checkbox_height=18,corner_radius=4).grid(row=i//3,column=i%3,sticky="w",padx=8,pady=2)

        section("Cabines")
        cbf=ctk.CTkFrame(m,fg_color="transparent");cbf.pack(anchor="w",padx=12)
        self.cbv={};ccb=self.ch.get("cabins",["business"])
        for i,(c,n) in enumerate(AVAILABLE_CABINS):
            v=ctk.BooleanVar(value=c in ccb);self.cbv[c]=v
            ctk.CTkCheckBox(cbf,text=n,variable=v,font=SF,height=26,checkbox_width=18,checkbox_height=18,corner_radius=4).grid(row=0,column=i,sticky="w",padx=8)

        section("Programas")
        pb=ctk.CTkFrame(m,fg_color="transparent");pb.pack(anchor="w",padx=12,pady=(0,4))
        ctk.CTkButton(pb,text="Todos",width=65,height=24,font=ctk.CTkFont(size=10),corner_radius=4,fg_color=C_GREEN_DARK,hover_color=C_GREEN,command=lambda:self._tp(True)).pack(side="left",padx=3)
        ctk.CTkButton(pb,text="Nenhum",width=65,height=24,font=ctk.CTkFont(size=10),corner_radius=4,fg_color=C_RED,hover_color="#dc2626",command=lambda:self._tp(False)).pack(side="left",padx=3)
        pf=ctk.CTkFrame(m,fg_color="transparent");pf.pack(fill="x",padx=12)
        self.pv={};cp=self.ch.get("programs",[p[0] for p in PROGRAMS])
        for i,(c,n) in enumerate(PROGRAMS):
            v=ctk.BooleanVar(value=c in cp);self.pv[c]=v
            ctk.CTkCheckBox(pf,text=n,variable=v,font=ctk.CTkFont(size=10),height=22,checkbox_width=16,checkbox_height=16,corner_radius=3).grid(row=i//3,column=i%3,sticky="w",padx=5,pady=1)

        # Opcoes
        section("Opcoes")
        self.ev=ctk.BooleanVar(value=self.ch.get("enabled",True))
        ctk.CTkCheckBox(m,text="Canal ativo",variable=self.ev,font=SF,height=26,checkbox_width=18,checkbox_height=18,corner_radius=4).pack(anchor="w",padx=12,pady=2)
        self.md_var=ctk.BooleanVar(value=self.ch.get("melhores_destinos",False))
        ctk.CTkCheckBox(m,text="Incluir Melhores Destinos",variable=self.md_var,font=SF,height=26,checkbox_width=18,checkbox_height=18,corner_radius=4).pack(anchor="w",padx=12,pady=2)

        # Botoes
        bf=ctk.CTkFrame(m,fg_color="transparent");bf.pack(fill="x",padx=12,pady=(12,8))
        ctk.CTkButton(bf,text="Salvar",width=120,height=38,font=ctk.CTkFont(size=12,weight="bold"),corner_radius=8,fg_color=C_GREEN_DARK,hover_color=C_GREEN,command=self._sv).pack(side="right",padx=4)
        ctk.CTkButton(bf,text="Cancelar",width=90,height=38,font=ctk.CTkFont(size=11),corner_radius=8,fg_color="transparent",border_width=1,border_color=("#ddd","#30363d"),text_color=("#666","#888"),hover_color=("#eee","#222"),command=self.destroy).pack(side="right",padx=4)

    def _tp(self,s):
        for v in self.pv.values():v.set(s)
    def _sv(self):
        nm=self.nv.get().strip();ci=self.cv.get().strip()
        if not nm:messagebox.showwarning("Aviso","Nome.",parent=self);return
        if not ci:messagebox.showwarning("Aviso","Chat ID.",parent=self);return
        origins=[o.strip().upper() for o in self.ori_var.get().split(",") if o.strip()]
        if not origins:messagebox.showwarning("Aviso","Origem.",parent=self);return
        rg=[c for c,v in self.rv.items() if v.get()];cb=[c for c,v in self.cbv.items() if v.get()];pg=[c for c,v in self.pv.items() if v.get()]
        if not rg or not cb or not pg:messagebox.showwarning("Aviso","Selecione regiao, cabine e programas.",parent=self);return
        avidest=[d.strip().upper() for d in self.avidest_var.get().split(",") if d.strip()]
        if self.cb:self.cb({"name":nm,"chat_id":ci,"origins":origins,"regions":rg,"cabins":cb,"programs":pg,"enabled":self.ev.get(),"melhores_destinos":self.md_var.get(),"avios_destinations":avidest},self.idx)
        self.destroy()

if __name__=="__main__":App().mainloop()
