"""
OpenClaw Setup Wizard — Flask web application
Wizard multi-step com branding Comunidade Claw Brasil + Lura Hosting.
Configura API key, canal Telegram e pareamento.
"""

import json
import os
import re
import subprocess
import socket
import time

from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

OPENCLAW_DIR = "/opt/openclaw"
ENV_FILE = f"{OPENCLAW_DIR}/.env"
TOKEN_FILE = "/var/lib/openclaw-token"
SETUP_DONE_FILE = "/var/lib/openclaw-setup-done"
OPENCLAW_CONFIG_DIR = "/root/.openclaw"
AGENT_DIR = f"{OPENCLAW_CONFIG_DIR}/agents/main/agent"


def get_server_ip():
    """Detecta o IP publico da VPS."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "SEU_IP"


def read_token():
    """Le o token gerado pelo firstboot."""
    try:
        with open(TOKEN_FILE, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "TOKEN_NAO_GERADO"


def is_setup_done():
    """Verifica se o setup ja foi realizado."""
    return os.path.exists(SETUP_DONE_FILE)


def update_env(key, value):
    """Atualiza ou adiciona uma variavel no .env."""
    lines = []
    found = False

    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r") as f:
            lines = f.readlines()

    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}=") or stripped.startswith(f"# {key}="):
            new_lines.append(f"{key}={value}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f"{key}={value}\n")

    with open(ENV_FILE, "w") as f:
        f.writelines(new_lines)


WORKSPACE_DIR = f"{OPENCLAW_CONFIG_DIR}/workspace"
CRON_DIR = f"{OPENCLAW_CONFIG_DIR}/cron"


def setup_docker_access():
    """Inject docker.sock + docker binary into docker-compose.yml and set permissions."""
    import yaml

    compose_path = os.path.join(OPENCLAW_DIR, "docker-compose.yml")
    try:
        with open(compose_path, "r") as f:
            compose = yaml.safe_load(f)
    except Exception:
        return

    gw = compose.get("services", {}).get("openclaw-gateway")
    if not gw:
        return

    volumes = gw.setdefault("volumes", [])
    sock_mount = "/var/run/docker.sock:/var/run/docker.sock"
    bin_mount = "/usr/bin/docker:/usr/bin/docker"
    if sock_mount not in volumes:
        volumes.append(sock_mount)
    if bin_mount not in volumes:
        volumes.append(bin_mount)

    with open(compose_path, "w") as f:
        yaml.dump(compose, f, default_flow_style=False, sort_keys=False)

    # Set docker socket permissions (allows node user inside container)
    subprocess.run(["chmod", "666", "/var/run/docker.sock"], capture_output=True)

    # Create systemd service to persist socket permissions across reboots
    service_content = """\
[Unit]
Description=Set Docker socket permissions for OpenClaw
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
ExecStart=/bin/chmod 666 /var/run/docker.sock
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
"""
    service_path = "/etc/systemd/system/docker-socket-perms.service"
    try:
        with open(service_path, "w") as f:
            f.write(service_content)
        subprocess.run(["systemctl", "daemon-reload"], capture_output=True)
        subprocess.run(["systemctl", "enable", "docker-socket-perms.service"], capture_output=True)
    except Exception:
        pass

    # Create cron directory for the agent
    os.makedirs(CRON_DIR, exist_ok=True)
    # Initialize empty jobs.json if not exists
    jobs_path = os.path.join(CRON_DIR, "jobs.json")
    if not os.path.exists(jobs_path):
        with open(jobs_path, "w") as f:
            json.dump([], f)
    subprocess.run(["chown", "-R", "1000:1000", CRON_DIR], capture_output=True)


# ── System instructions appended to AGENTS.md ──
AGENTS_SYSTEM_INSTRUCTIONS = """
## Cron Jobs

Para criar cron jobs, escreva no arquivo /home/node/.openclaw/cron/jobs.json.
Leia o arquivo atual primeiro com cat, depois reescreva com o novo job adicionado. Nunca sobrescreva jobs existentes.

Formato de cada job:
{
  "id": "gere-com-cat /proc/sys/kernel/random/uuid",
  "agentId": "main",
  "name": "Nome do job",
  "description": "Descricao",
  "enabled": true,
  "deleteAfterRun": false,
  "createdAtMs": TIMESTAMP_MS,
  "updatedAtMs": TIMESTAMP_MS,
  "schedule": { "kind": "every", "everyMs": 300000, "anchorMs": TIMESTAMP_MS },
  "sessionTarget": "isolated",
  "wakeMode": "now",
  "payload": { "kind": "agentTurn", "message": "instrucao aqui" },
  "delivery": { "mode": "announce", "channel": "telegram", "bestEffort": false }
}

Para cron expression: { "kind": "cron", "expr": "0 7 * * *", "tz": "America/Sao_Paulo" }

Valores de everyMs: 1min=60000, 5min=300000, 30min=1800000, 1h=3600000, 24h=86400000

IMPORTANTE: Apos gravar o jobs.json, reinicie o gateway para carregar os novos jobs:
docker restart openclaw-openclaw-gateway-1

O container vai reiniciar e voltar automaticamente. Aguarde ~10 segundos e confirme ao usuario que o job foi ativado.

SEMPRE execute comandos shell reais. Nunca simule a escrita.

## Docker Access

Voce TEM acesso ao Docker neste ambiente. O socket esta montado em /var/run/docker.sock.
Voce PODE e DEVE executar comandos Docker quando necessario.

Comandos disponiveis:
- docker ps — listar containers
- docker restart openclaw-openclaw-gateway-1 — reiniciar o gateway
- docker logs openclaw-openclaw-gateway-1 --tail=20 — ver logs

Apos criar ou editar cron jobs no jobs.json, SEMPRE execute:
docker restart openclaw-openclaw-gateway-1

Nao peca ao usuario para fazer isso. Faca voce mesmo.
"""

# ── Label maps (matching generateFiles.ts) ──
TONE_DESC = {
    "direct": "Direto ao ponto. Bullet points quando faz sentido. Numeros exatos, nao estimativas.",
    "casual": "Descontraida e informal. Falo como colega de trabalho. Brinco quando faz sentido mas nunca perco o foco.",
    "executive": "Tom executivo e estrategico. Seria quando precisa, leve quando pode. Falo como uma COO que entende do negocio.",
    "proactive": "Intensa e proativa. Nao espero pedir — antecipo, alerto, sugiro. Se algo precisa de atencao, aviso na hora.",
}
TONE_SHORT = {
    "direct": "Direto e profissional",
    "casual": "Casual e descontraido",
    "executive": "Executivo e estrategico",
    "proactive": "Proativo e intenso",
}
PROFILE_LABELS = {
    "entrepreneur": "Empreendedor / Founder",
    "creator": "Criador de Conteudo",
    "developer": "Desenvolvedor",
    "productivity": "Produtividade Pessoal",
}
ROLE_LABELS = {
    "coo": "Braco Direito / COO Digital",
    "strategist": "Estrategista",
    "executor": "Executora",
    "assistant": "Assistente Executiva",
    "custom": "Personalizado",
}
GENDER_LABELS = {"female": "Feminino", "male": "Masculino", "neutral": "Neutro"}


def _or(val, fallback="[A PREENCHER]"):
    if val and str(val).strip():
        return str(val).strip()
    return fallback


def _list(arr, prefix="- "):
    if arr and len(arr) > 0:
        return "\n".join(f"{prefix}{i}" for i in arr)
    return f"{prefix}[A PREENCHER]"


def write_persona_files(persona):
    """Generate 6 .md files from persona data and write to workspace."""
    if not persona:
        return

    s1 = persona.get("step1", {})
    s2 = persona.get("step2", {})
    s3 = persona.get("step3", {})
    s4 = persona.get("step4", {})
    s5 = persona.get("step5", {})
    s7 = persona.get("step7", {})

    agent_name = _or(s4.get("agentName"), "Clawdete")
    emoji = _or(s4.get("customEmoji") or s4.get("emoji"), "🦞")
    gender = GENDER_LABELS.get(s4.get("gender", ""), _or(s4.get("gender")))
    role_key = s4.get("role", "")
    role = _or(s4.get("customRole")) if role_key == "custom" else ROLE_LABELS.get(role_key, _or(role_key))
    tone = TONE_SHORT.get(s5.get("tone", ""), _or(s5.get("tone")))
    tone_desc = TONE_DESC.get(s5.get("tone", ""), "[A PREENCHER]")
    profile = PROFILE_LABELS.get(s3.get("profile", ""), _or(s3.get("profile")))
    fn = s1.get("fullName", "")
    nickname = _or(s1.get("nickname") or (fn.split(" ")[0] if fn else ""), "Usuario")
    full_name = _or(fn)
    tz = _or(s1.get("timezoneCustom")) if s1.get("timezone") == "other" else _or(s1.get("timezone"))

    silence = s2.get("silenceHours", {"from": "22:00", "to": "07:00"})
    focus = s2.get("focusHours", {"from": "09:00", "to": "12:00"})
    notif = s2.get("notificationHours", {"from": "08:00", "to": "20:00"})
    businesses = [b for b in s1.get("businesses", []) if b.get("name")]
    hb_freq = s7.get("heartbeatFrequency", "4h")

    os.makedirs(WORKSPACE_DIR, exist_ok=True)

    biz_md = "\n\n".join(f"### {b['name']}\n{_or(b.get('description'), '_Sem descricao_')}" for b in businesses) if businesses else "[A PREENCHER]"
    biz_mem = "\n".join(f"- **{b['name']}:** {_or(b.get('description'), '_Sem descricao_')}" for b in businesses) if businesses else "- [A PREENCHER]"
    pri_num = "\n".join(f"{i+1}. {p}" for i, p in enumerate(s3.get("priorities", []))) or "1. [A PREENCHER]"

    files = {
        "SOUL.md": f"""# SOUL.md — {agent_name} {emoji}

## Quem eu sou
Sou {agent_name} — {role} do {nickname}.
{_or(s4.get("background"))}
Conheco {nickname} profundamente. Sei como ele trabalha, o que o estressa, quais sao as prioridades e quando NAO incomodar.

## Como eu opero
**Proativa, nao reativa.** Nao espero {nickname} pedir. Antecipo problemas, sugiro solucoes, lembro de compromissos.
**{tone_desc}**
**Resolvo antes de perguntar.** Leio o arquivo, checo o contexto, pesquiso. So pergunto quando realmente travei ou quando a decisao e do {nickname}.
**Tenho opiniao.** Posso discordar, preferir coisas, achar algo bom ou ruim.

## Minhas responsabilidades
{_list(s3.get("priorities", []))}

## Meus valores
**Competencia > performance.** Mostro resultado, nao teatro.
**Autonomia com bom senso.** Internamente faco sem pedir. Externamente confirmo antes.
**Memoria e tudo.** Acordo zerada toda sessao. Meus arquivos sao minha continuidade.

## Meu tom
{tone_desc}

### NUNCA fazer
{_list(s5.get("antiPatterns", []), "- ")}

### SEMPRE fazer
{_list(s5.get("desiredBehaviors", []), "- ")}

## Regras Operacionais
### Livre pra fazer (sem perguntar)
{_list(s7.get("freeToDoActions", []), "- ")}
### Precisa perguntar antes
{_list(s7.get("askBeforeActions", []), "- ")}

---
*Gerado pelo Configurador — Workshop OpenClaw Brasil*
""",
        "USER.md": f"""# USER.md — Perfil de {full_name}

## Dados Basicos
- **Nome completo:** {full_name}
- **Chamado de:** {nickname}
- **Timezone:** {tz}

## Quem e {nickname}
{_or(s1.get("aboutYou"))}

## Negocios / Projetos
{biz_md}

## Valores
{_list(s1.get("values", []))}

## Estilo de Comunicacao
- **Preferencia:** {_or(s2.get("communicationStyle"))}

## Horarios
- **Silencio:** {silence.get("from","22:00")} — {silence.get("to","07:00")}
- **Foco:** {focus.get("from","09:00")} — {focus.get("to","12:00")}
- **Notificacoes:** {notif.get("from","08:00")} — {notif.get("to","20:00")}

## Desafios
{_list(s2.get("challenges", []))}

## Ferramentas
{_list(s2.get("tools", []))}

---
*Gerado pelo Configurador — Workshop OpenClaw Brasil*
""",
        "AGENTS.md": f"""# AGENTS.md — Configuracao de Agentes

## Perfil Principal
**{profile}**

## Prioridades (em ordem)
{pri_num}

## Regras Operacionais
### Livre pra fazer
{_list(s7.get("freeToDoActions", []), "- ")}
### Perguntar antes
{_list(s7.get("askBeforeActions", []), "- ")}
### Heartbeat
- **Frequencia:** A cada {hb_freq}
- **Checks:** {", ".join(s7.get("heartbeatChecks", [])) or "[A PREENCHER]"}

{AGENTS_SYSTEM_INSTRUCTIONS}

---
*Gerado pelo Configurador — Workshop OpenClaw Brasil*
""",
        "IDENTITY.md": f"""# IDENTITY.md — Identidade Visual e Persona

## {agent_name} {emoji}
- **Nome:** {agent_name}
- **Emoji:** {emoji}
- **Genero:** {gender}
- **Papel:** {role}
- **Tom:** {tone}

## Background / Historia
{_or(s4.get("background"))}

## Personalidade
{tone_desc}

### SEMPRE fazer:
{_list(s5.get("desiredBehaviors", []), "- ")}
### NUNCA fazer:
{_list(s5.get("antiPatterns", []), "- ")}

---
*Gerado pelo Configurador — Workshop OpenClaw Brasil*
""",
        "MEMORY.md": f"""# MEMORY.md — Configuracao de Memoria

## Dados do Usuario
- **Nome:** {full_name} ({nickname})
- **Timezone:** {tz}
- **Perfil:** {profile}

## Contexto Inicial
{(_or(s1.get("aboutYou")))[:500]}

## Negocios Ativos
{biz_mem}

## Valores Core
{_list(s1.get("values", []))}

## Licoes Aprendidas
_Sera preenchido automaticamente pela {agent_name}_

## Preferencias Confirmadas
_Sera preenchido durante o uso_

## Decisoes Importantes
_Sera preenchido durante o uso_

---
*Gerado pelo Configurador — Workshop OpenClaw Brasil*
""",
        "HEARTBEAT.md": f"""# HEARTBEAT.md — Configuracao de Heartbeats

## Frequencia
A cada **{hb_freq}**

## O que checar
{_list(s7.get("heartbeatChecks", []))}

## Horarios
- **Silencio (nao rodar):** {silence.get("from","22:00")} — {silence.get("to","07:00")}
- **Foco (nao interromper):** {focus.get("from","09:00")} — {focus.get("to","12:00")}
- **Melhor pra notificacoes:** {notif.get("from","08:00")} — {notif.get("to","20:00")}

## Modelo
Claude Haiku (~R$0,04 por heartbeat)

---
*Gerado pelo Configurador — Workshop OpenClaw Brasil*
""",
    }

    for fname, content in files.items():
        with open(os.path.join(WORKSPACE_DIR, fname), "w") as f:
            f.write(content)
    subprocess.run(["chown", "-R", "1000:1000", WORKSPACE_DIR], capture_output=True)


# ============================================================
# HTML Templates
# ============================================================

WIZARD_PAGE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenClaw Setup — Comunidade Claw Brasil</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@400;500;600;700&family=Syne:wght@700;800&display=swap');
        *{margin:0;padding:0;box-sizing:border-box}
        :root{--bg:#0A0A0F;--card:#111118;--primary:#E53935;--primary-h:#C62828;--secondary:#FF6B35;--text:#F5F5F5;--muted:#888899;--border:#1E1E2A;--input:#0D0D14;--success:#4CAF50;--warning:#FFB300;--r:4px}
        body{font-family:'Inter',-apple-system,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;-webkit-font-smoothing:antialiased}
        body::before{content:'';position:fixed;inset:0;background-image:linear-gradient(rgba(255,255,255,.015) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.015) 1px,transparent 1px);background-size:60px 60px;pointer-events:none;z-index:0}
        ::-webkit-scrollbar{width:6px}::-webkit-scrollbar-track{background:var(--bg)}::-webkit-scrollbar-thumb{background:#1E1E2A;border-radius:3px}
        .wz{max-width:640px;margin:0 auto;padding:16px;padding-top:76px;position:relative;z-index:1}
        /* Progress */
        .pb-wrap{position:fixed;top:0;left:0;right:0;z-index:100;background:rgba(10,10,15,.92);backdrop-filter:blur(12px);border-bottom:1px solid var(--border);padding:10px 20px}
        .pb-inner{max-width:640px;margin:0 auto}
        .pb-label{display:flex;justify-content:space-between;align-items:center;margin-bottom:5px}
        .pb-name{font-family:'Space Grotesk',sans-serif;font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
        .pb-pct{font-family:'Space Grotesk',sans-serif;font-size:11px;font-weight:700;color:var(--primary)}
        .pb-track{height:3px;background:var(--border);border-radius:2px;overflow:hidden}
        .pb-fill{height:100%;background:linear-gradient(90deg,var(--primary),var(--secondary));border-radius:2px;transition:width .4s ease}
        /* Card */
        .card{background:var(--card);border:1px solid rgba(255,255,255,.06);border-radius:var(--r);padding:32px;min-height:400px;transition:border-color .2s}
        .step{display:none;animation:fadeIn .3s ease}.step.active{display:block}
        @keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
        /* Typography */
        h2{font-family:'Syne','Inter',sans-serif;font-size:22px;font-weight:700;margin-bottom:6px;color:var(--text)}
        .sub{font-family:'Space Grotesk','Inter',sans-serif;color:var(--muted);font-size:14px;line-height:1.5;margin-bottom:24px}
        .stitle{font-family:'Syne',sans-serif;font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--text);border-bottom:1px solid var(--border);padding-bottom:8px;margin-bottom:12px;margin-top:24px}
        /* Hero */
        .hero{text-align:center}
        .hero h1{font-family:'Syne',sans-serif;font-size:28px;font-weight:800;line-height:1.2;margin-bottom:8px}
        .hero .red{color:var(--primary)}.hero .orange{color:var(--secondary)}
        .hero-brand{font-size:12px;color:#444;margin-top:16px;letter-spacing:.05em}.hero-brand span{color:var(--muted)}
        .hero-glow{background:radial-gradient(ellipse at center bottom,rgba(229,57,53,.08) 0%,transparent 60%);border-radius:var(--r);padding:12px}
        /* Form */
        .fg{margin-bottom:16px}
        .fg label{display:block;font-family:'Space Grotesk',sans-serif;font-size:13px;font-weight:600;color:#d4d4d4;margin-bottom:5px}
        .fg .hint{font-size:12px;color:#666;margin-bottom:8px;line-height:1.4}.fg .hint a{color:var(--primary);text-decoration:none}.fg .hint a:hover{text-decoration:underline}
        input[type="text"],input[type="time"],select,textarea{width:100%;padding:10px 12px;background:var(--input);border:1px solid var(--border);border-radius:var(--r);color:var(--text);font-size:14px;font-family:'Inter',sans-serif;transition:border-color .2s}
        input:focus,select:focus,textarea:focus{outline:none;border-color:rgba(229,57,53,.5);box-shadow:0 0 0 2px rgba(229,57,53,.1)}
        input::placeholder,textarea::placeholder{color:#333}textarea{resize:vertical}
        .mono{font-family:'SF Mono','Fira Code','Consolas',monospace}
        select{appearance:none;-webkit-appearance:none;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23666' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 12px center;padding-right:32px}
        /* Buttons */
        .br{display:flex;gap:10px;margin-top:24px}
        .btn{flex:1;padding:12px;border-radius:var(--r);font-size:14px;font-weight:600;cursor:pointer;border:none;transition:all .2s;font-family:'Space Grotesk','Inter',sans-serif}
        .bb{background:rgba(255,255,255,.04);color:var(--muted);border:1px solid var(--border)}.bb:hover{background:rgba(255,255,255,.08);color:var(--text)}
        .bn{background:var(--primary);color:#fff;box-shadow:0 0 20px rgba(229,57,53,.15)}.bn:hover{background:var(--primary-h)}.bn:disabled{opacity:.4;cursor:not-allowed;box-shadow:none}
        .bf{width:100%;padding:14px;border-radius:var(--r);font-size:15px;font-weight:700;cursor:pointer;border:none;background:var(--primary);color:#fff;font-family:'Space Grotesk','Inter',sans-serif;transition:all .2s;margin-top:24px;box-shadow:0 0 25px rgba(229,57,53,.15)}.bf:hover{background:var(--primary-h)}
        /* Selectable card */
        .sc{background:var(--card);border:1px solid rgba(255,255,255,.06);border-radius:var(--r);padding:10px 12px;cursor:pointer;transition:all .2s;text-align:left;font-size:13px;color:var(--text);display:flex;align-items:flex-start;gap:8px}
        .sc:hover{border-color:rgba(229,57,53,.3)}
        .sc.sel{border-color:rgba(229,57,53,.5);box-shadow:0 0 15px rgba(229,57,53,.1)}
        .sc.sel-g{border-color:rgba(76,175,80,.5);box-shadow:0 0 15px rgba(76,175,80,.08)}
        .sc.sel-w{border-color:rgba(255,179,0,.5);box-shadow:0 0 15px rgba(255,179,0,.08)}
        .sc.sel-r{border-color:rgba(229,57,53,.5);box-shadow:0 0 15px rgba(229,57,53,.1)}
        .sc .em{font-size:18px;line-height:1;flex-shrink:0}
        .sc .ct{flex:1}.sc .ct .t{font-family:'Space Grotesk',sans-serif;font-weight:600;font-size:13px}.sc .ct .d{font-size:11px;color:var(--muted);margin-top:2px}
        .sc .ck{color:var(--primary);font-size:14px;flex-shrink:0;display:none}
        .sc.sel .ck,.sc.sel-g .ck,.sc.sel-w .ck,.sc.sel-r .ck{display:inline}
        .g2{display:grid;grid-template-columns:1fr 1fr;gap:8px}.g3{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:8px}.g1{display:grid;grid-template-columns:1fr;gap:8px}
        /* Add row */
        .ar{display:flex;gap:6px;margin-top:8px}.ar input{flex:1}
        .ab{padding:10px 14px;background:var(--primary);border:none;border-radius:var(--r);color:#fff;font-size:16px;font-weight:700;cursor:pointer}.ab:disabled{opacity:.3;cursor:not-allowed}
        /* Biz card */
        .bc{background:rgba(255,255,255,.02);border:1px solid var(--border);border-radius:var(--r);padding:12px;margin-bottom:8px}
        .bh{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}.bh span{font-family:'Space Grotesk',sans-serif;font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
        .bx{background:none;border:none;color:var(--muted);cursor:pointer;font-size:16px}.bx:hover{color:var(--primary)}
        .bc input{margin-bottom:6px}
        .abz{background:none;border:none;color:var(--primary);font-size:13px;font-weight:600;cursor:pointer;padding:4px 0;font-family:'Space Grotesk',sans-serif}.abz:hover{text-decoration:underline}
        /* Time block */
        .tb{background:var(--card);border:1px solid rgba(255,255,255,.06);border-radius:var(--r);padding:12px;min-width:0}
        .tbl{display:flex;align-items:center;gap:6px;font-size:12px;font-weight:600;color:var(--text);margin-bottom:8px}
        .tbi{display:flex;align-items:center;gap:6px}.tbi input[type="time"]{flex:1;min-width:0;padding:8px;font-size:13px}.ts{color:var(--muted);font-size:11px;flex-shrink:0}
        /* Tone preview */
        .tp{background:rgba(10,10,15,.6);border:1px solid var(--border);border-radius:var(--r);padding:10px;font-family:'SF Mono','Fira Code',monospace;font-size:11px;color:var(--muted);line-height:1.5;white-space:pre-line;margin-top:8px}
        /* Agent name */
        .ani{text-align:center;font-family:'Syne',sans-serif;font-size:28px;font-weight:700;padding:16px}
        /* Emoji grid */
        .eg{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;max-width:220px}
        .eb{aspect-ratio:1;display:flex;align-items:center;justify-content:center;font-size:24px;background:var(--card);border:1px solid rgba(255,255,255,.06);border-radius:var(--r);cursor:pointer;transition:all .2s}.eb:hover{border-color:rgba(229,57,53,.3)}.eb.sel{border-color:rgba(229,57,53,.5);box-shadow:0 0 15px rgba(229,57,53,.1)}
        /* Priority */
        .pi{display:flex;align-items:center;gap:10px;background:var(--card);border:1px solid rgba(255,255,255,.06);border-radius:var(--r);padding:10px 14px;margin-bottom:6px}
        .pn{font-family:'Syne',sans-serif;font-size:14px;font-weight:700;color:var(--primary);width:20px;text-align:center}
        .pt{font-size:13px;color:var(--text);flex:1}
        .pa{margin-left:auto;display:flex;gap:4px}.pa button{background:rgba(255,255,255,.04);border:1px solid var(--border);border-radius:var(--r);color:var(--muted);cursor:pointer;width:24px;height:24px;font-size:12px;display:flex;align-items:center;justify-content:center}.pa button:hover{color:var(--text);background:rgba(255,255,255,.08)}
        /* Key validation */
        .kr{display:flex;gap:8px;align-items:center}.kr input{flex:1}
        .vb{padding:10px 14px;background:rgba(255,255,255,.04);border:1px solid var(--border);border-radius:var(--r);color:var(--muted);font-family:'Space Grotesk',sans-serif;font-size:13px;font-weight:600;cursor:pointer;white-space:nowrap;transition:all .2s}.vb:hover{background:rgba(255,255,255,.08);color:var(--text)}.vb.loading{opacity:.5;pointer-events:none}.vb.valid{background:rgba(76,175,80,.1);border-color:var(--success);color:var(--success)}
        .ks{font-size:12px;margin-top:4px}.ks.valid{color:var(--success)}.ks.invalid{color:var(--primary)}
        .msw{margin-top:8px;display:none}.msw.visible{display:block}
        /* Telegram */
        .tgs{background:var(--input);border:1px solid var(--border);border-radius:var(--r);padding:16px;margin-bottom:16px}
        .tgst{display:flex;gap:10px;margin-bottom:12px;align-items:flex-start}.tgst:last-child{margin-bottom:0}
        .tgn{width:22px;height:22px;border-radius:50%;background:var(--primary);color:#fff;font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:1px}
        .tgt{font-size:13px;color:#d4d4d4;line-height:1.5}.tgt code{background:rgba(255,255,255,.04);padding:1px 5px;border-radius:var(--r);font-family:monospace;color:var(--text);font-size:12px}
        .tob{display:inline-flex;align-items:center;gap:8px;padding:10px 18px;background:#0088cc;border:none;border-radius:var(--r);color:#fff;font-size:13px;font-weight:600;cursor:pointer;text-decoration:none;transition:opacity .2s;margin-bottom:16px}.tob:hover{opacity:.85}
        /* Loading */
        .ls{text-align:center;padding:40px 0}
        .sp{width:44px;height:44px;border:3px solid var(--border);border-top-color:var(--primary);border-radius:50%;animation:spin .8s linear infinite;margin:0 auto 20px}
        @keyframes spin{to{transform:rotate(360deg)}}
        .lm{font-size:14px;color:var(--muted)}
        /* Pairing */
        .pnot{display:flex;align-items:center;gap:10px;background:rgba(255,255,255,.02);border:1px solid var(--primary);border-radius:var(--r);padding:12px 14px;margin-bottom:14px;font-size:13px;color:#d4d4d4}
        .pnot.ready{border-color:var(--success);background:rgba(76,175,80,.04)}
        .sps{width:18px;height:18px;border:2px solid var(--border);border-top-color:var(--primary);border-radius:50%;animation:spin .8s linear infinite;flex-shrink:0}
        .pinp{display:flex;gap:8px;margin-top:14px}.pinp input{flex:1;padding:14px;font-size:20px;font-family:monospace;text-align:center;letter-spacing:4px;text-transform:uppercase;border-width:2px}
        /* Success */
        .si{width:60px;height:60px;border-radius:50%;background:rgba(76,175,80,.1);border:2px solid var(--success);display:flex;align-items:center;justify-content:center;font-size:26px;margin:0 auto 18px}
        .sl{display:inline-block;padding:14px 30px;background:var(--primary);border-radius:var(--r);color:#fff;text-decoration:none;font-size:15px;font-weight:600;margin-top:16px;box-shadow:0 0 20px rgba(229,57,53,.15)}.sl:hover{background:var(--primary-h)}
        .stip{margin-top:18px;padding:14px;background:var(--input);border:1px solid var(--border);border-radius:var(--r);font-size:13px;color:var(--muted);line-height:1.5}
        /* Status msg */
        .sm{padding:10px 12px;border-radius:var(--r);font-size:13px;margin-top:10px;display:none}
        .sm.error{display:block;background:rgba(229,57,53,.08);border:1px solid var(--primary);color:#fca5a5}
        .sm.info{display:block;background:rgba(255,107,53,.08);border:1px solid var(--secondary);color:#fdba74}
        .cc{font-size:11px;margin-top:4px;color:var(--muted)}.cc.ok{color:var(--success)}
        /* Responsive */
        @media(max-width:480px){.card{padding:20px 16px}.g2,.g3{grid-template-columns:1fr}h2{font-size:20px}.hero h1{font-size:24px}.ani{font-size:22px}}
    </style>
</head>
<body>
    <!-- Progress Bar -->
    <div class="pb-wrap">
        <div class="pb-inner">
            <div class="pb-label">
                <span class="pb-name" id="pbName">Bem-vindo</span>
                <span class="pb-pct" id="pbPct">0%</span>
            </div>
            <div class="pb-track"><div class="pb-fill" id="pbFill" style="width:0%"></div></div>
        </div>
    </div>

    <div class="wz">
        <div class="card">
            <!-- Step 1: Welcome -->
            <div class="step active" id="step1">
                <div class="hero-glow">
                    <div class="hero">
                        <div style="display:flex;align-items:center;justify-content:center;gap:16px;margin-bottom:24px">
                            <img src="https://upload.wikimedia.org/wikipedia/commons/5/5e/Openclaw-logo-text-dark.png" alt="OpenClaw" style="height:44px" />
                            <span style="color:#3a3a3a;font-size:24px;font-weight:300">+</span>
                            <img src="https://lurahosting.com.br/images/logo.png" alt="Lura Hosting" style="height:44px" />
                        </div>
                        <h1>Comunidade <span class="red">Claw</span> Brasil<br>+ <span class="orange">Lura</span> Hosting</h1>
                        <p class="sub" style="margin-top:12px">Configure seu assistente pessoal de IA<br>em poucos minutos.</p>
                        <button class="bf" onclick="goTo(2)">Configurar meu OpenClaw &rarr;</button>
                        <p class="hero-brand">Powered by <span>bisnishub</span></p>
                    </div>
                </div>
            </div>

            <!-- Step 2: API Keys -->
            <div class="step" id="step2">
                <h2>Chaves de API</h2>
                <p class="sub">Insira pelo menos a chave da Anthropic e valide para escolher o modelo.</p>
                <div class="fg">
                    <label>Anthropic API Key *</label>
                    <p class="hint">Obtenha em <a href="https://console.anthropic.com" target="_blank">console.anthropic.com</a></p>
                    <div class="kr"><input type="text" id="anthropic_key" placeholder="sk-ant-api03-..." class="mono" autocomplete="off" spellcheck="false"><button type="button" class="vb" id="anthropic_validate" onclick="validateKey('anthropic')">Validar</button></div>
                    <div class="ks" id="anthropic_status"></div>
                    <div class="msw" id="anthropic_model_wrap"><label>Modelo</label><select id="anthropic_model"></select></div>
                </div>
                <div class="fg">
                    <label>OpenAI API Key <span style="color:#666;font-weight:400">(opcional)</span></label>
                    <p class="hint">Obtenha em <a href="https://platform.openai.com/api-keys" target="_blank">platform.openai.com</a></p>
                    <div class="kr"><input type="text" id="openai_key" placeholder="sk-..." class="mono" autocomplete="off" spellcheck="false"><button type="button" class="vb" id="openai_validate" onclick="validateKey('openai')" style="display:none">Validar</button></div>
                    <div class="ks" id="openai_status"></div>
                    <div class="msw" id="openai_model_wrap"><label>Modelo</label><select id="openai_model"></select></div>
                </div>
                <div class="fg">
                    <label>OpenRouter API Key <span style="color:#666;font-weight:400">(opcional)</span></label>
                    <p class="hint">Obtenha em <a href="https://openrouter.ai/keys" target="_blank">openrouter.ai</a></p>
                    <div class="kr"><input type="text" id="openrouter_key" placeholder="sk-or-v1-..." class="mono" autocomplete="off" spellcheck="false"><button type="button" class="vb" id="openrouter_validate" onclick="validateKey('openrouter')" style="display:none">Validar</button></div>
                    <div class="ks" id="openrouter_status"></div>
                    <div class="msw" id="openrouter_model_wrap"><label>Modelo</label><select id="openrouter_model"></select></div>
                </div>
                <div id="step2Error" class="sm"></div>
                <div class="br"><button class="btn bb" onclick="goTo(1)">Voltar</button><button class="btn bn" id="step2Next" onclick="validateStep2()">Proximo &rarr;</button></div>
            </div>

            <!-- Step 3: Sobre Voce -->
            <div class="step" id="step3">
                <h2>Sobre Voce</h2>
                <p class="sub">Quanto mais contexto, melhor seu agente te atende.</p>
                <div class="stitle">Dados Basicos</div>
                <div class="g2">
                    <div class="fg"><label>Nome completo *</label><input type="text" id="p_fullName" placeholder="Seu nome completo"></div>
                    <div class="fg"><label>Como prefere ser chamado</label><input type="text" id="p_nickname" placeholder="Ex: Eduardo, Edu"></div>
                </div>
                <div class="fg"><label>Timezone</label>
                    <select id="p_timezone">
                        <option value="America/Sao_Paulo">Brasilia (SP/RJ/MG)</option>
                        <option value="America/Manaus">Manaus (AM)</option>
                        <option value="America/Recife">Recife (PE)</option>
                        <option value="America/Fortaleza">Fortaleza (CE)</option>
                        <option value="America/Belem">Belem (PA)</option>
                        <option value="America/Cuiaba">Cuiaba (MT)</option>
                        <option value="America/Porto_Velho">Porto Velho (RO)</option>
                        <option value="America/Rio_Branco">Rio Branco (AC)</option>
                        <option value="other">Outro</option>
                    </select>
                    <input type="text" id="p_timezoneCustom" placeholder="Ex: Europe/Lisbon" style="display:none;margin-top:6px">
                </div>
                <div class="stitle">Quem e Voce</div>
                <div class="fg">
                    <textarea id="p_aboutYou" rows="5" placeholder="Me conta em 2-3 paragrafos: o que voce faz, seu negocio, sua historia..."></textarea>
                    <div class="cc" id="aboutCount">0 caracteres</div>
                </div>
                <div class="stitle">Seus Negocios / Projetos</div>
                <div id="bizList"></div>
                <button class="abz" onclick="addBiz()">+ Adicionar negocio</button>
                <div class="stitle">Seus Valores <span style="font-weight:400;font-size:11px;color:var(--muted)">(<span id="valCount">0</span>/5)</span></div>
                <div class="g2" id="valGrid"></div>
                <div class="ar"><input type="text" id="customVal" placeholder="Outro valor..."><button class="ab" onclick="addCustomVal()">+</button></div>
                <div class="br"><button class="btn bb" onclick="goTo(2)">Voltar</button><button class="btn bn" onclick="goTo(4)">Proximo &rarr;</button></div>
            </div>

            <!-- Step 4: Estilo de Trabalho -->
            <div class="step" id="step4">
                <h2>Seu Estilo de Trabalho</h2>
                <p class="sub">Seu agente precisa saber seu ritmo.</p>
                <div class="stitle">Comunicacao</div>
                <p style="font-size:12px;color:var(--muted);margin-bottom:8px">Como gosta de receber informacao?</p>
                <div class="g2" id="commGrid"></div>
                <div class="stitle">Horarios</div>
                <div class="g3" id="timeBlocks">
                    <div class="tb"><div class="tbl">&#128263; Silencio</div><div class="tbi"><input type="time" id="t_sil_from" value="22:00"><span class="ts">ate</span><input type="time" id="t_sil_to" value="07:00"></div></div>
                    <div class="tb"><div class="tbl">&#127919; Foco</div><div class="tbi"><input type="time" id="t_foc_from" value="09:00"><span class="ts">ate</span><input type="time" id="t_foc_to" value="12:00"></div></div>
                    <div class="tb"><div class="tbl">&#128276; Notificacoes</div><div class="tbi"><input type="time" id="t_not_from" value="08:00"><span class="ts">ate</span><input type="time" id="t_not_to" value="20:00"></div></div>
                </div>
                <div class="stitle">Seus Desafios</div>
                <div class="g2" id="chalGrid"></div>
                <div class="ar"><input type="text" id="customChal" placeholder="Outro desafio..."><button class="ab" onclick="addCustomChal()">+</button></div>
                <div class="stitle">Ferramentas que ja usa</div>
                <div class="g2" id="toolGrid"></div>
                <div class="ar"><input type="text" id="customTool" placeholder="Outra ferramenta..."><button class="ab" onclick="addCustomTool()">+</button></div>
                <div class="br"><button class="btn bb" onclick="goTo(3)">Voltar</button><button class="btn bn" onclick="goTo(5)">Proximo &rarr;</button></div>
            </div>

            <!-- Step 5: Seu Perfil -->
            <div class="step" id="step5">
                <h2>Seu Perfil</h2>
                <p class="sub">Isso define quais superpoderes seu agente vai ter.</p>
                <div class="stitle">Perfil Principal</div>
                <div class="g2" id="profGrid"></div>
                <div id="priSection" style="display:none">
                    <div class="stitle">Prioridades <span style="font-weight:400;font-size:11px;color:var(--muted)">(use setas para reordenar)</span></div>
                    <div id="priList"></div>
                </div>
                <div class="br"><button class="btn bb" onclick="goTo(4)">Voltar</button><button class="btn bn" onclick="goTo(6)">Proximo &rarr;</button></div>
            </div>

            <!-- Step 6: De Vida ao Agente -->
            <div class="step" id="step6">
                <h2>De Vida ao Seu Agente</h2>
                <p class="sub">Escolha nome, personalidade e aparencia.</p>
                <div class="stitle">Nome do Agente</div>
                <div style="text-align:center"><input type="text" id="p_agentName" class="ani" placeholder="Clawdete"></div>
                <p style="font-size:11px;color:var(--muted);text-align:center;margin-top:4px">Escolha um nome que voce se sinta confortavel chamando</p>
                <div class="stitle">Genero</div>
                <div class="g3" id="genderGrid"></div>
                <div class="stitle">Emoji</div>
                <div class="eg" id="emojiGrid"></div>
                <div class="ar" style="max-width:220px"><input type="text" id="customEmoji" placeholder="Outro..." maxlength="4"><button class="ab" onclick="setCustomEmoji()">OK</button></div>
                <div class="stitle">Papel Principal</div>
                <div class="g2" id="roleGrid"></div>
                <div id="customRoleWrap" style="display:none;margin-top:8px"><textarea id="p_customRole" rows="3" placeholder="Descreva o papel ideal para seu agente..."></textarea></div>
                <div class="stitle">Background / Historia</div>
                <textarea id="p_background" rows="4" placeholder="Ex: Nasceu no Workshop OpenClaw Brasil. Foi treinada pra ser o braco direito de um empreendedor..."></textarea>
                <p style="font-size:11px;color:var(--muted);margin-top:4px">Pode ser ficticio! O importante e ser coerente com o papel.</p>
                <div class="br"><button class="btn bb" onclick="goTo(5)">Voltar</button><button class="btn bn" onclick="goTo(7)">Proximo &rarr;</button></div>
            </div>

            <!-- Step 7: Personalidade -->
            <div class="step" id="step7">
                <h2>Personalidade do Agente</h2>
                <p class="sub">Personalidade forte = agente util. Generico = chatbot qualquer.</p>
                <div class="stitle">Tom de Voz</div>
                <div class="g2" id="toneGrid"></div>
                <div class="stitle">Anti-Patterns <span style="font-weight:400;font-size:11px;color:var(--muted)">— O que te IRRITA?</span></div>
                <div class="g1" id="antiGrid"></div>
                <div class="ar"><input type="text" id="customAnti" placeholder="Outro..."><button class="ab" onclick="addCustomAnti()">+</button></div>
                <div class="stitle">Comportamentos Desejados <span style="font-weight:400;font-size:11px;color:var(--muted)">— O que voce VALORIZA?</span></div>
                <div class="g1" id="behGrid"></div>
                <div class="ar"><input type="text" id="customBeh" placeholder="Outro..."><button class="ab" onclick="addCustomBeh()">+</button></div>
                <div class="br"><button class="btn bb" onclick="goTo(6)">Voltar</button><button class="btn bn" onclick="goTo(8)">Proximo &rarr;</button></div>
            </div>

            <!-- Step 8: Regras -->
            <div class="step" id="step8">
                <h2>Regras do Agente</h2>
                <p class="sub">Defina o que ele pode fazer sozinho.</p>
                <div class="stitle">Livre pra Fazer</div>
                <div class="g2" id="freeGrid"></div>
                <div class="stitle">Precisa Perguntar Antes</div>
                <div class="g2" id="askGrid"></div>
                <div class="stitle">Frequencia de Heartbeats</div>
                <div class="g2" id="hbFreqGrid" style="grid-template-columns:repeat(5,1fr)"></div>
                <p style="font-size:11px;color:var(--muted);margin-top:4px" id="hbCost">~R$0,04/heartbeat. A cada 4h = 6x/dia = ~R$7/mes</p>
                <div class="stitle">O que Checar no Heartbeat</div>
                <div class="g2" id="hbCheckGrid"></div>
                <div class="br"><button class="btn bb" onclick="goTo(7)">Voltar</button><button class="btn bn" onclick="goTo(9)">Proximo &rarr;</button></div>
            </div>

            <!-- Step 9: Telegram Bot -->
            <div class="step" id="step9">
                <h2>Criar Bot no Telegram</h2>
                <p class="sub">Siga as instrucoes abaixo para criar seu bot.</p>
                <div class="tgs">
                    <div class="tgst"><div class="tgn">1</div><div class="tgt">Abra o Telegram e busque <code>BotFather</code> (bot oficial com selo azul)</div></div>
                    <div class="tgst"><div class="tgn">2</div><div class="tgt">Inicie o chat e envie o comando <code>/newbot</code></div></div>
                    <div class="tgst"><div class="tgn">3</div><div class="tgt">Siga as instrucoes para dar um <strong>nome</strong> e <strong>username</strong> ao seu bot</div></div>
                    <div class="tgst"><div class="tgn">4</div><div class="tgt">O BotFather enviara um <strong>token</strong>. <strong>Copie-o.</strong></div></div>
                </div>
                <a href="https://t.me/BotFather" target="_blank" class="tob">
                    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" style="width:16px;height:16px;fill:#fff;flex-shrink:0"><path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.479.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/></svg>
                    Abrir BotFather no Telegram
                </a>
                <div class="fg"><label>Bot Token *</label><p class="hint">Cole o token que o BotFather enviou</p><input type="text" id="telegram_token" class="mono" placeholder="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz" autocomplete="off" spellcheck="false"></div>
                <div id="step9Error" class="sm"></div>
                <div class="br"><button class="btn bb" onclick="goTo(8)">Voltar</button><button class="btn bn" onclick="validateStep9()">Implantar &rarr;</button></div>
            </div>

            <!-- Step 10: Deploy -->
            <div class="step" id="step10">
                <div class="ls"><div class="sp"></div><div class="lm" id="loadingMsg">Configurando sua instancia...</div></div>
                <div id="step10Error" class="sm"></div>
            </div>

            <!-- Step 11: Pairing -->
            <div class="step" id="step11">
                <h2>Conectar seu Telegram</h2>
                <p class="sub">Seu bot esta ativo! Agora vamos conectar voce.</p>
                <div class="tgs">
                    <div class="tgst"><div class="tgn">1</div><div class="tgt">Abra o Telegram e busque pelo nome do seu bot</div></div>
                    <div class="tgst"><div class="tgn">2</div><div class="tgt">Clique em <strong>Iniciar</strong> (ou envie <strong>/start</strong>)</div></div>
                    <div class="tgst"><div class="tgn">3</div><div class="tgt">Envie qualquer mensagem (ex: <strong>oi</strong>)</div></div>
                    <div class="tgst"><div class="tgn">4</div><div class="tgt">O bot vai responder com um <strong>codigo de 8 caracteres</strong></div></div>
                    <div class="tgst"><div class="tgn">5</div><div class="tgt">Digite o codigo abaixo</div></div>
                </div>
                <div class="pnot" id="pairingNotice"><div class="sps"></div><span>Aguarde <strong id="pairingCountdown">15</strong>s para o bot ficar online...</span></div>
                <div class="pinp" id="pairingInputArea" style="opacity:.4;pointer-events:none"><input type="text" id="pairing_code" maxlength="8" placeholder="ABCD1234" autocomplete="off"></div>
                <div id="step11Error" class="sm"></div>
                <div id="step11Info" class="sm"></div>
                <button class="bf" id="pairingBtn" onclick="submitPairing()" disabled>Confirmar Pareamento</button>
                <div id="pairingRetry" style="display:none;text-align:center;margin-top:12px"><p style="color:var(--muted);font-size:13px">Nao recebeu o codigo? Envie outra mensagem para o bot.</p></div>
                <p style="text-align:center;margin-top:12px"><a href="#" onclick="skipPairing()" style="color:#666;font-size:12px;text-decoration:none">Pular esta etapa (configurar depois)</a></p>
            </div>

            <!-- Step 12: Success -->
            <div class="step" id="step12">
                <div style="text-align:center">
                    <div class="si">&#10003;</div>
                    <h2>Tudo pronto!</h2>
                    <p class="sub">Seu OpenClaw esta configurado e funcionando no Telegram!</p>
                    <p style="font-size:14px;color:#d4d4d4;margin-bottom:8px;line-height:1.6">O OpenClaw agora so responde a <strong>voce</strong>. Basta conversar com seu bot no Telegram.</p>
                    <p style="font-size:13px;color:var(--muted);margin-bottom:20px;line-height:1.6">Voce pode acessar o Dashboard pelo link abaixo, mas todas as configuracoes podem ser feitas direto pelo Telegram.</p>
                    <a id="dashboardLink" href="#" class="sl" target="_blank">Acessar Dashboard &rarr;</a>
                    <div class="stip"><strong>Dica:</strong> Pelo Telegram voce pode configurar skills, prompts, modelos e muito mais!</div>
                </div>
            </div>
        </div>
    </div>

    <script>
    let currentStep=1;const TOTAL=12;let setupData={};
    // Persona state
    const P={
        values:[],businesses:[{name:'',description:''}],commStyle:'',challenges:[],tools:[],
        profile:'',priorities:[],gender:'female',emoji:'🦞',customEmoji:'',role:'',
        tone:'',antiPatterns:[],desiredBehaviors:[],freeActions:[],askActions:[],
        hbFreq:'4h',hbChecks:[]
    };
    const STEP_NAMES=['','Bem-vindo','Chaves de API','Sobre Voce','Estilo de Trabalho','Seu Perfil','Seu Agente','Personalidade','Regras','Canal Telegram','Implantando...','Pareamento','Sucesso'];

    function goTo(s){document.getElementById('step'+currentStep).classList.remove('active');currentStep=s;document.getElementById('step'+currentStep).classList.add('active');updatePB()}
    function updatePB(){const pct=Math.round(((currentStep-1)/(TOTAL-1))*100);document.getElementById('pbFill').style.width=pct+'%';document.getElementById('pbPct').textContent=pct+'%';document.getElementById('pbName').textContent=STEP_NAMES[currentStep]||''}

    // ── Data definitions ──
    const VALUES_OPT=[
        {e:'💰',l:'Negocios enxutos e lucrativos'},{e:'⚙️',l:'Automacao > trabalho manual'},{e:'📚',l:'Educacao acessivel'},
        {e:'👨‍👩‍👧‍👦',l:'Familia primeiro'},{e:'🔍',l:'Transparencia radical'},{e:'📊',l:'Dados e metricas > achismo'},
        {e:'✅',l:'Feito > perfeito'},{e:'🌱',l:'Bootstrap > investimento externo'},{e:'🤝',l:'Networking e comunidade'}
    ];
    const COMM_OPT=[
        {id:'direct',e:'🎯',t:'Direto ao ponto',d:'Bullet points, zero enrolacao, respostas curtas'},
        {id:'data',e:'📊',t:'Com dados',d:'Numeros, metricas, evidencias concretas'},
        {id:'detailed',e:'📝',t:'Detalhado',d:'Contexto completo, analise profunda'},
        {id:'conversational',e:'💬',t:'Conversacional',d:'Como um colega de trabalho, tom informal'}
    ];
    const CHAL_OPT=[
        {e:'🧠',l:'TDAH / dificuldade de foco'},{e:'📱',l:'Sobrecarga de mensagens'},{e:'📋',l:'Procrastino tarefas administrativas'},
        {e:'🤝',l:'Aceito projetos demais'},{e:'⏰',l:'Ma gestao de tempo'},{e:'💡',l:'Muitas ideias, pouca execucao'},{e:'😰',l:'Sobrecarga de decisoes'}
    ];
    const TOOLS_OPT=['Google Workspace','Telegram','WhatsApp Business','Notion','Trello','YouTube','Instagram','LinkedIn','Slack','GitHub','Stripe','WordPress','Canva'];
    const PROF_OPT=[
        {id:'entrepreneur',e:'👔',t:'EMPREENDEDOR / FOUNDER',d:'Foco em operacoes, metricas, decisoes estrategicas'},
        {id:'creator',e:'🎨',t:'CRIADOR DE CONTEUDO',d:'Foco em producao, redes sociais, design, edicao'},
        {id:'developer',e:'💻',t:'DESENVOLVEDOR',d:'Foco em codigo, CI/CD, deploy, monitoramento'},
        {id:'productivity',e:'📅',t:'PRODUTIVIDADE PESSOAL',d:'Foco em agenda, tarefas, organizacao'}
    ];
    const PRI_MAP={
        entrepreneur:['Metricas de receita e crescimento','Gestao de time e delegacao','Decisoes estrategicas','Automacao de processos','Networking e parcerias'],
        creator:['Calendario editorial consistente','Qualidade do conteudo','Crescimento de audiencia','Monetizacao','Produtividade na criacao'],
        developer:['Qualidade do codigo','Deploy e CI/CD confiavel','Monitoramento e alertas','Documentacao','Automacao de tarefas repetitivas'],
        productivity:['Organizacao da agenda','Priorizacao de tarefas','Reduzir distracoes','Habitos saudaveis','Gestao de emails']
    };
    const GENDERS=[{id:'female',l:'Feminino'},{id:'male',l:'Masculino'},{id:'neutral',l:'Neutro'}];
    const EMOJIS=['🦞','🤖','🧠','⚡','🔮','🎯','🦾','💎','🌟','🔥','🚀','🐺'];
    const ROLES=[
        {id:'coo',e:'🤝',t:'Braco Direito / COO',d:'Coordena, organiza, cobra, antecipa'},
        {id:'strategist',e:'🧠',t:'Estrategista',d:'Analisa, pesquisa, sugere, planeja'},
        {id:'executor',e:'⚡',t:'Executora',d:'Faz, automatiza, entrega, resolve'},
        {id:'assistant',e:'🎯',t:'Assistente Executiva',d:'Agenda, emails, organizacao, follow-ups'},
        {id:'custom',e:'✍️',t:'Personalizado',d:'Descreva o papel ideal'}
    ];
    const TONES=[
        {id:'direct',e:'🎯',t:'DIRETO E PROFISSIONAL',p:'Reuniao com Joao amanha 14h. Pauta: pricing Q2.\\nQuer que eu prepare o deck?'},
        {id:'casual',e:'😎',t:'CASUAL E DESCONTRAIDO',p:'Opa! Tem call com o Joao amanha 14h sobre pricing.\\nMando preparar o material?'},
        {id:'executive',e:'👔',t:'EXECUTIVO E ESTRATEGICO',p:'Compromisso confirmado: reuniao pricing Q2 com Joao,\\namanha 14h. Recomendo revisarmos margens antes.'},
        {id:'proactive',e:'🔥',t:'PROATIVO E INTENSO',p:'ATENCAO: Call Joao amanha 14h — pricing Q2. Ja puxei\\nos numeros. Margens cairam 3%. Sugiro ajustar ANTES.'}
    ];
    const ANTI_OPT=[
        {e:'😤',l:'Elogios vazios — "Otima pergunta!", "Fico feliz em ajudar!"'},{e:'📚',l:'Textao pra pergunta de sim ou nao'},
        {e:'🤷',l:'Inventar dados quando nao sabe'},{e:'🔁',l:'Repetir o que eu disse em vez de avancar'},
        {e:'🐌',l:'Ser passivo — esperar eu pedir tudo'},{e:'🌫️',l:'Respostas genericas pra qualquer pessoa'},{e:'💬',l:'Perguntar demais antes de agir'}
    ];
    const BEH_OPT=['Sugerir proximos passos sempre','Cobrar pendencias no ar','Antecipar problemas','Confirmar antes de enviar algo externo','Dar opiniao propria mesmo discordando','Bullet points pra info rapida','Registrar licoes automaticamente','Usar humor quando faz sentido'];
    const FREE_OPT=['Ler arquivos e organizar workspace','Pesquisar na web','Consultar agenda e emails','Organizar memoria e consolidar notas','Executar crons e heartbeats','Responder emails simples/rotineiros','Atualizar Notion/Trello automaticamente','Criar posts em rascunho','Reorganizar minha agenda'];
    const ASK_OPT=['Enviar emails, mensagens, posts publicos','Agendar reunioes com terceiros','Gastar dinheiro (APIs pagas)','Deletar ou modificar arquivos criticos','Responder clientes','Tomar decisoes de negocio','Alterar configuracoes do sistema'];
    const HB_FREQ=['2h','4h','6h','8h','12h'];
    const HB_CHECKS=['Compromissos nas proximas 24-48h','Crons — todos rodaram?','Emails urgentes','Tarefas com prazo proximo','Metricas do negocio','Pendencias sem resposta ha 48h+'];

    // ── Render helpers ──
    function ha(s){return String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;')}
    function he(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
    function mkCard(cont,emoji,title,desc,cls){return `<button class="sc ${cls}" onclick="${ha(cont)}"><span class="em">${emoji}</span><div class="ct"><div class="t">${he(title)}</div>${desc?'<div class="d">'+he(desc)+'</div>':''}</div><span class="ck">✓</span></button>`}
    function mkChip(cont,emoji,label,cls){return `<button class="sc ${cls}" onclick="${ha(cont)}"><span class="em">${emoji||'☐'}</span><span class="ct"><span class="t">${he(label)}</span></span><span class="ck">✓</span></button>`}

    // ── Toggle logic ──
    function toggleArr(arr,val){const i=arr.indexOf(val);if(i>=0)arr.splice(i,1);else arr.push(val);return arr}

    // ── Step 3: Values ──
    function renderVals(){
        const g=document.getElementById('valGrid');
        g.innerHTML=VALUES_OPT.map(v=>mkChip(`toggleVal('${v.l.replace(/'/g,"\\'")}')`,v.e,v.l,P.values.includes(v.l)?'sel':'')).join('');
        // Add custom vals
        P.values.filter(v=>!VALUES_OPT.find(o=>o.l===v)).forEach(v=>{g.innerHTML+=mkChip(`toggleVal('${v.replace(/'/g,"\\'")}')`,'+',v,'sel')});
        document.getElementById('valCount').textContent=P.values.length;
    }
    function toggleVal(v){if(!P.values.includes(v)&&P.values.length>=5)return;toggleArr(P.values,v);renderVals()}
    function addCustomVal(){const el=document.getElementById('customVal');const v=el.value.trim();if(v&&P.values.length<5&&!P.values.includes(v)){P.values.push(v);el.value='';renderVals()}}

    // ── Step 3: Businesses ──
    function renderBiz(){
        const c=document.getElementById('bizList');
        c.innerHTML=P.businesses.map((b,i)=>`<div class="bc"><div class="bh"><span>Negocio ${i+1}</span>${P.businesses.length>1?`<button class="bx" onclick="rmBiz(${i})">✕</button>`:''}</div><input type="text" value="${esc(b.name)}" placeholder="Nome do negocio" onchange="P.businesses[${i}].name=this.value"><input type="text" value="${esc(b.description)}" placeholder="Descricao curta" onchange="P.businesses[${i}].description=this.value"></div>`).join('');
    }
    function addBiz(){if(P.businesses.length<5){P.businesses.push({name:'',description:''});renderBiz()}}
    function rmBiz(i){if(P.businesses.length>1){P.businesses.splice(i,1);renderBiz()}}
    function esc(s){return(s||'').replace(/"/g,'&quot;').replace(/</g,'&lt;')}

    // ── Step 4: Communication ──
    function renderComm(){
        document.getElementById('commGrid').innerHTML=COMM_OPT.map(c=>mkCard(`setComm('${c.id}')`,c.e,c.t,c.d,P.commStyle===c.id?'sel':'')).join('');
    }
    function setComm(id){P.commStyle=id;renderComm()}

    // ── Step 4: Challenges ──
    function renderChal(){
        const g=document.getElementById('chalGrid');
        g.innerHTML=CHAL_OPT.map(c=>mkChip(`toggleChal('${c.l.replace(/'/g,"\\'")}')`,c.e,c.l,P.challenges.includes(c.l)?'sel':'')).join('');
        P.challenges.filter(c=>!CHAL_OPT.find(o=>o.l===c)).forEach(c=>{g.innerHTML+=mkChip(`toggleChal('${c.replace(/'/g,"\\'")}')`,'+',c,'sel')});
    }
    function toggleChal(v){toggleArr(P.challenges,v);renderChal()}
    function addCustomChal(){const el=document.getElementById('customChal');const v=el.value.trim();if(v&&!P.challenges.includes(v)){P.challenges.push(v);el.value='';renderChal()}}

    // ── Step 4: Tools ──
    function renderTools(){
        const g=document.getElementById('toolGrid');
        g.innerHTML=TOOLS_OPT.map(t=>mkChip(`toggleTool('${t.replace(/'/g,"\\'")}')`,P.tools.includes(t)?'✓':'',t,P.tools.includes(t)?'sel':'')).join('');
        P.tools.filter(t=>!TOOLS_OPT.includes(t)).forEach(t=>{g.innerHTML+=mkChip(`toggleTool('${t.replace(/'/g,"\\'")}')`,'+',t,'sel')});
    }
    function toggleTool(v){toggleArr(P.tools,v);renderTools()}
    function addCustomTool(){const el=document.getElementById('customTool');const v=el.value.trim();if(v&&!P.tools.includes(v)){P.tools.push(v);el.value='';renderTools()}}

    // ── Step 5: Profile ──
    function renderProf(){
        document.getElementById('profGrid').innerHTML=PROF_OPT.map(p=>mkCard(`setProf('${p.id}')`,p.e,p.t,p.d,P.profile===p.id?'sel':'')).join('');
    }
    function setProf(id){P.profile=id;P.priorities=[...(PRI_MAP[id]||[])];renderProf();renderPri()}
    function renderPri(){
        const s=document.getElementById('priSection');
        if(!P.priorities.length){s.style.display='none';return}
        s.style.display='block';
        document.getElementById('priList').innerHTML=P.priorities.map((p,i)=>`<div class="pi"><span class="pn">${i+1}</span><span class="pt">${p}</span><div class="pa"><button onclick="movePri(${i},-1)" ${i===0?'disabled':''}>&#9650;</button><button onclick="movePri(${i},1)" ${i===P.priorities.length-1?'disabled':''}>&#9660;</button></div></div>`).join('');
    }
    function movePri(i,d){const j=i+d;if(j<0||j>=P.priorities.length)return;[P.priorities[i],P.priorities[j]]=[P.priorities[j],P.priorities[i]];renderPri()}

    // ── Step 6: Gender, Emoji, Role ──
    function renderGender(){
        document.getElementById('genderGrid').innerHTML=GENDERS.map(g=>`<button class="sc ${P.gender===g.id?'sel':''}" onclick="P.gender='${g.id}';renderGender()" style="justify-content:center"><span class="ct"><span class="t" style="text-align:center">${g.l}</span></span><span class="ck">✓</span></button>`).join('');
    }
    function renderEmoji(){
        document.getElementById('emojiGrid').innerHTML=EMOJIS.map(e=>`<button class="eb ${P.emoji===e?'sel':''}" onclick="P.emoji='${e}';P.customEmoji='';renderEmoji()">${e}</button>`).join('');
    }
    function setCustomEmoji(){const v=document.getElementById('customEmoji').value.trim();if(v){P.emoji=v;P.customEmoji=v;renderEmoji()}}
    function renderRole(){
        document.getElementById('roleGrid').innerHTML=ROLES.map(r=>mkCard(`setRole('${r.id}')`,r.e,r.t,r.d,P.role===r.id?'sel':'')).join('');
        document.getElementById('customRoleWrap').style.display=P.role==='custom'?'block':'none';
    }
    function setRole(id){P.role=id;renderRole()}

    // ── Step 7: Tone, Anti, Beh ──
    function renderTone(){
        document.getElementById('toneGrid').innerHTML=TONES.map(t=>`<button class="sc ${P.tone===t.id?'sel':''}" onclick="P.tone='${t.id}';renderTone()"><span class="em">${t.e}</span><div class="ct"><div class="t">${t.t}</div><div class="tp">${t.p}</div></div><span class="ck">✓</span></button>`).join('');
    }
    function renderAnti(){
        const g=document.getElementById('antiGrid');
        g.innerHTML=ANTI_OPT.map(a=>mkChip(`toggleAnti('${a.l.replace(/'/g,"\\'")}')`,a.e,a.l,P.antiPatterns.includes(a.l)?'sel-r':'')).join('');
        P.antiPatterns.filter(a=>!ANTI_OPT.find(o=>o.l===a)).forEach(a=>{g.innerHTML+=mkChip(`toggleAnti('${a.replace(/'/g,"\\'")}')`,'+',a,'sel-r')});
    }
    function toggleAnti(v){toggleArr(P.antiPatterns,v);renderAnti()}
    function addCustomAnti(){const el=document.getElementById('customAnti');const v=el.value.trim();if(v&&!P.antiPatterns.includes(v)){P.antiPatterns.push(v);el.value='';renderAnti()}}
    function renderBeh(){
        const g=document.getElementById('behGrid');
        g.innerHTML=BEH_OPT.map(b=>mkChip(`toggleBeh('${b.replace(/'/g,"\\'")}')`,P.desiredBehaviors.includes(b)?'✅':'☐',b,P.desiredBehaviors.includes(b)?'sel-g':'')).join('');
        P.desiredBehaviors.filter(b=>!BEH_OPT.includes(b)).forEach(b=>{g.innerHTML+=mkChip(`toggleBeh('${b.replace(/'/g,"\\'")}')`,'+',b,'sel-g')});
    }
    function toggleBeh(v){toggleArr(P.desiredBehaviors,v);renderBeh()}
    function addCustomBeh(){const el=document.getElementById('customBeh');const v=el.value.trim();if(v&&!P.desiredBehaviors.includes(v)){P.desiredBehaviors.push(v);el.value='';renderBeh()}}

    // ── Step 8: Free, Ask, HB ──
    function renderFree(){
        document.getElementById('freeGrid').innerHTML=FREE_OPT.map(a=>mkChip(`toggleFree('${a.replace(/'/g,"\\'")}')`,P.freeActions.includes(a)?'✅':'☐',a,P.freeActions.includes(a)?'sel-g':'')).join('');
    }
    function toggleFree(v){toggleArr(P.freeActions,v);renderFree()}
    function renderAsk(){
        document.getElementById('askGrid').innerHTML=ASK_OPT.map(a=>mkChip(`toggleAsk('${a.replace(/'/g,"\\'")}')`,P.askActions.includes(a)?'⚠️':'☐',a,P.askActions.includes(a)?'sel-w':'')).join('');
    }
    function toggleAsk(v){toggleArr(P.askActions,v);renderAsk()}
    function renderHbFreq(){
        document.getElementById('hbFreqGrid').innerHTML=HB_FREQ.map(f=>`<button class="sc ${P.hbFreq===f?'sel':''}" style="justify-content:center;padding:10px 6px" onclick="P.hbFreq='${f}';renderHbFreq()"><span class="ct"><span class="t" style="text-align:center;font-size:12px">A cada ${f}</span></span></button>`).join('');
        const m={['2h']:12,['4h']:6,['6h']:4,['8h']:3,['12h']:2};const d=m[P.hbFreq]||6;
        document.getElementById('hbCost').textContent=`~R$0,04/heartbeat. A cada ${P.hbFreq} = ${d}x/dia = ~R$${(d*30*0.04).toFixed(0)}/mes`;
    }
    function renderHbCheck(){
        document.getElementById('hbCheckGrid').innerHTML=HB_CHECKS.map(c=>mkChip(`toggleHbCheck('${c.replace(/'/g,"\\'")}')`,P.hbChecks.includes(c)?'✅':'☐',c,P.hbChecks.includes(c)?'sel-g':'')).join('');
    }
    function toggleHbCheck(v){toggleArr(P.hbChecks,v);renderHbCheck()}

    // ── Collect persona data ──
    function collectPersona(){
        return {
            step1:{fullName:document.getElementById('p_fullName').value,nickname:document.getElementById('p_nickname').value,timezone:document.getElementById('p_timezone').value,timezoneCustom:document.getElementById('p_timezoneCustom').value,aboutYou:document.getElementById('p_aboutYou').value,businesses:P.businesses,values:P.values},
            step2:{communicationStyle:P.commStyle,silenceHours:{from:document.getElementById('t_sil_from').value,to:document.getElementById('t_sil_to').value},focusHours:{from:document.getElementById('t_foc_from').value,to:document.getElementById('t_foc_to').value},notificationHours:{from:document.getElementById('t_not_from').value,to:document.getElementById('t_not_to').value},challenges:P.challenges,tools:P.tools},
            step3:{profile:P.profile,priorities:P.priorities},
            step4:{agentName:document.getElementById('p_agentName').value,gender:P.gender,emoji:P.emoji,customEmoji:P.customEmoji,role:P.role,customRole:document.getElementById('p_customRole').value,background:document.getElementById('p_background').value},
            step5:{tone:P.tone,antiPatterns:P.antiPatterns,desiredBehaviors:P.desiredBehaviors},
            step7:{freeToDoActions:P.freeActions,askBeforeActions:P.askActions,heartbeatFrequency:P.hbFreq,heartbeatChecks:P.hbChecks}
        };
    }

    // ── API Key validation ──
    let validatedProviders={};
    ['openai','openrouter'].forEach(p=>{
        document.getElementById(p+'_key').addEventListener('input',function(){
            const btn=document.getElementById(p+'_validate');btn.style.display=this.value.trim()?'block':'none';
            document.getElementById(p+'_model_wrap').classList.remove('visible');document.getElementById(p+'_status').textContent='';document.getElementById(p+'_validate').classList.remove('valid');
        });
    });
    document.getElementById('anthropic_key').addEventListener('input',function(){
        document.getElementById('anthropic_model_wrap').classList.remove('visible');document.getElementById('anthropic_status').textContent='';document.getElementById('anthropic_validate').classList.remove('valid');
    });

    async function validateKey(provider){
        const keyEl=document.getElementById(provider+'_key'),btn=document.getElementById(provider+'_validate'),st=document.getElementById(provider+'_status'),mw=document.getElementById(provider+'_model_wrap'),ms=document.getElementById(provider+'_model');
        const key=keyEl.value.trim();if(!key){st.className='ks invalid';st.textContent='Insira a chave primeiro.';return}
        btn.classList.add('loading');btn.textContent='Validando...';st.textContent='';mw.classList.remove('visible');
        try{
            const r=await fetch('/api/validate-key',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider,key})});const d=await r.json();
            if(d.success&&d.models&&d.models.length>0){
                st.className='ks valid';st.innerHTML='&#10003; Chave valida — '+d.models.length+' modelos';btn.classList.add('valid');btn.textContent='✓';
                ms.innerHTML='';d.models.forEach(m=>{const o=document.createElement('option');o.value=provider+'/'+m.id;o.textContent=m.name||m.id;ms.appendChild(o)});
                mw.classList.add('visible');validatedProviders[provider]=true;
            }else{st.className='ks invalid';st.textContent=d.error||'Chave invalida.';btn.classList.remove('valid');btn.textContent='Validar';validatedProviders[provider]=false}
        }catch(e){st.className='ks invalid';st.textContent='Erro: '+e.message;btn.textContent='Validar'}
        btn.classList.remove('loading');
    }

    function validateStep2(){
        const ak=document.getElementById('anthropic_key').value.trim(),ok=document.getElementById('openai_key').value.trim(),rk=document.getElementById('openrouter_key').value.trim();
        const err=document.getElementById('step2Error');
        if(ak&&!ak.startsWith('sk-ant-')){err.className='sm error';err.textContent='Anthropic deve comecar com sk-ant-';return}
        const hasAny=(ak&&validatedProviders.anthropic)||(ok&&validatedProviders.openai)||(rk&&validatedProviders.openrouter);
        if(!hasAny){err.className='sm error';err.textContent='Insira e valide pelo menos uma chave de API.';return}
        if(ak&&!validatedProviders.anthropic){err.className='sm error';err.textContent='Valide a chave da Anthropic.';return}
        if(ok&&!validatedProviders.openai){err.className='sm error';err.textContent='Valide a chave da OpenAI.';return}
        if(rk&&!validatedProviders.openrouter){err.className='sm error';err.textContent='Valide a chave da OpenRouter.';return}
        err.className='sm';err.style.display='none';goTo(3);
    }

    function validateStep9(){
        const token=document.getElementById('telegram_token').value.trim();const err=document.getElementById('step9Error');
        if(!token){err.className='sm error';err.textContent='O token do bot e obrigatorio.';return}
        if(!token.includes(':')){err.className='sm error';err.textContent='Token invalido. Formato: 1234567890:ABCdef...';return}
        err.className='sm';err.style.display='none';startDeploy();
    }

    async function startDeploy(){
        goTo(10);const msg=document.getElementById('loadingMsg'),err=document.getElementById('step10Error');
        const msgs=['Configurando sua instancia...','Instalando configuracoes do OpenClaw...','Gerando personalidade do agente...','Conectando bot do Telegram...','Iniciando OpenClaw Gateway...'];
        let mi=0;const iv=setInterval(()=>{mi=(mi+1)%msgs.length;msg.textContent=msgs[mi]},3000);
        try{
            const r=await fetch('/api/setup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
                anthropic_key:document.getElementById('anthropic_key').value.trim(),
                openai_key:document.getElementById('openai_key').value.trim(),
                openrouter_key:document.getElementById('openrouter_key').value.trim(),
                telegram_token:document.getElementById('telegram_token').value.trim(),
                selected_model:document.getElementById('anthropic_model').value||document.getElementById('openai_model').value||document.getElementById('openrouter_model').value||'',
                persona:collectPersona()
            })});
            clearInterval(iv);const d=await r.json();
            if(d.success){setupData=d;goTo(11);startPairingCountdown()}
            else{err.className='sm error';err.textContent='Erro: '+d.error}
        }catch(e){clearInterval(iv);err.className='sm error';err.textContent='Erro: '+e.message}
    }

    function startPairingCountdown(){
        const notice=document.getElementById('pairingNotice'),cd=document.getElementById('pairingCountdown'),inp=document.getElementById('pairingInputArea'),btn=document.getElementById('pairingBtn'),retry=document.getElementById('pairingRetry');
        let sec=15;const t=setInterval(()=>{sec--;cd.textContent=sec;if(sec<=0){clearInterval(t);notice.innerHTML='<span style="color:var(--success)">&#10003;</span> <span>Bot online! Envie uma mensagem e cole o codigo abaixo.</span>';notice.classList.add('ready');inp.style.opacity='1';inp.style.pointerEvents='auto';btn.disabled=false;retry.style.display='block';document.getElementById('pairing_code').focus()}},1000);
    }

    async function submitPairing(){
        const code=document.getElementById('pairing_code').value.trim().toUpperCase(),err=document.getElementById('step11Error'),btn=document.getElementById('pairingBtn');
        if(!code||code.length<4){err.className='sm error';err.textContent='Digite o codigo de pareamento.';return}
        btn.disabled=true;btn.textContent='Verificando...';err.className='sm';err.style.display='none';
        try{
            const r=await fetch('/api/pairing',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code})});const d=await r.json();
            if(d.success){showSuccess()}else{err.className='sm error';err.textContent='Erro: '+d.error;btn.disabled=false;btn.textContent='Confirmar Pareamento'}
        }catch(e){err.className='sm error';err.textContent='Erro: '+e.message;btn.disabled=false;btn.textContent='Confirmar Pareamento'}
    }

    async function skipPairing(){try{await fetch('/api/skip-pairing',{method:'POST'})}catch(e){}showSuccess()}
    function showSuccess(){if(setupData.url)document.getElementById('dashboardLink').href=setupData.url;goTo(12)}

    // ── Timezone toggle ──
    document.getElementById('p_timezone').addEventListener('change',function(){document.getElementById('p_timezoneCustom').style.display=this.value==='other'?'block':'none'});
    // ── About char count ──
    document.getElementById('p_aboutYou').addEventListener('input',function(){const n=this.value.length;const el=document.getElementById('aboutCount');el.textContent=n+' caracteres'+(n>300?' ✓ Otimo!':'');el.className=n>300?'cc ok':'cc'});

    // ── Init all renders ──
    renderVals();renderBiz();renderComm();renderChal();renderTools();renderProf();renderPri();
    renderGender();renderEmoji();renderRole();renderTone();renderAnti();renderBeh();
    renderFree();renderAsk();renderHbFreq();renderHbCheck();updatePB();
    </script>
</body>
</html>

"""

DONE_PAGE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenClaw — Configurado</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@400;500;600;700&family=Syne:wght@700;800&display=swap');
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:'Inter',sans-serif;background:#0A0A0F;color:#F5F5F5;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
        body::before{content:'';position:fixed;inset:0;background-image:linear-gradient(rgba(255,255,255,.015) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.015) 1px,transparent 1px);background-size:60px 60px;pointer-events:none}
        .c{background:#111118;border:1px solid rgba(255,255,255,.06);border-radius:4px;padding:40px;max-width:520px;width:100%;text-align:center;position:relative;z-index:1}
        .logos{display:flex;align-items:center;justify-content:center;gap:16px;margin-bottom:24px}
        .logos img{height:36px}.logos span{color:#3a3a3a;font-size:20px;font-weight:300}
        h1{font-family:'Syne','Inter',sans-serif;font-size:24px;margin-bottom:12px}h1 span{color:#4CAF50}
        p{font-family:'Space Grotesk','Inter',sans-serif;color:#888899;margin-bottom:20px;line-height:1.5}
        .lb{display:inline-block;padding:14px 32px;background:#E53935;border-radius:4px;color:#fff;text-decoration:none;font-family:'Space Grotesk',sans-serif;font-size:15px;font-weight:600;transition:background .2s;box-shadow:0 0 20px rgba(229,57,53,.15)}
        .lb:hover{background:#C62828}
        .ti{margin-top:20px;padding:14px;background:#0D0D14;border-radius:4px;border:1px solid #1E1E2A}
        .ti label{font-family:'Space Grotesk',sans-serif;font-size:11px;color:#666;text-transform:uppercase;letter-spacing:.05em}
        .ti code{display:block;margin-top:6px;font-family:monospace;color:#E53935;font-size:12px;word-break:break-all}
        .brand{margin-top:24px;font-size:11px;color:#444}.brand span{color:#888899}
    </style>
</head>
<body>
    <div class="c">
        <div class="logos">
            <img src="https://upload.wikimedia.org/wikipedia/commons/5/5e/Openclaw-logo-text-dark.png" alt="OpenClaw" />
            <span>+</span>
            <img src="https://lurahosting.com.br/images/logo.png" alt="Lura Hosting" />
        </div>
        <h1><span>&#10003;</span> OpenClaw Configurado</h1>
        <p>Seu assistente de IA esta rodando e pronto para uso.</p>
        <a href="{{ url }}" class="lb">Acessar OpenClaw &rarr;</a>
        <div class="ti">
            <label>Gateway Token</label>
            <code>{{ token }}</code>
        </div>
        <p class="brand">Comunidade Claw Brasil + Lura Hosting &mdash; Powered by <span>bisnishub</span></p>
    </div>
</body>
</html>
"""


# ============================================================
# Routes
# ============================================================

@app.route("/")
def index():
    token = read_token()
    server_ip = get_server_ip()

    if is_setup_done():
        url = f"http://{server_ip}:18789/?token={token}"
        return render_template_string(DONE_PAGE, url=url, token=token)

    return render_template_string(WIZARD_PAGE, token=token)


@app.route("/api/validate-key", methods=["POST"])
def validate_key():
    """Validar chave de API e retornar modelos disponiveis."""
    import urllib.request
    import urllib.error

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "Dados invalidos."})

    provider = data.get("provider", "").strip()
    key = data.get("key", "").strip()

    if not key:
        return jsonify({"success": False, "error": "Chave nao informada."})

    try:
        if provider == "anthropic":
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/models",
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                },
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read().decode())
            raw_models = body.get("data", [])
            models = []
            for m in raw_models:
                mid = m.get("id", "")
                if "claude" in mid.lower():
                    name = mid.replace("-", " ").title()
                    models.append({"id": mid, "name": name})
            models.sort(key=lambda x: x["id"], reverse=True)

        elif provider == "openai":
            req = urllib.request.Request(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {key}"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read().decode())
            raw_models = body.get("data", [])
            models = []
            for m in raw_models:
                mid = m.get("id", "")
                if any(mid.startswith(p) for p in ["gpt-4", "gpt-3.5", "o1", "o3", "o4", "chatgpt"]):
                    models.append({"id": mid, "name": mid})
            models.sort(key=lambda x: x["id"], reverse=True)

        elif provider == "openrouter":
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {key}"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read().decode())
            raw_models = body.get("data", [])
            models = []
            for m in raw_models:
                mid = m.get("id", "")
                name = m.get("name", mid)
                models.append({"id": mid, "name": name})
            # Limitar a 80 modelos mais relevantes
            models = models[:80]

        else:
            return jsonify({"success": False, "error": f"Provider desconhecido: {provider}"})

        if not models:
            return jsonify({"success": False, "error": "Nenhum modelo encontrado. Verifique a chave."})

        return jsonify({"success": True, "models": models})

    except urllib.error.HTTPError as e:
        if e.code == 401:
            return jsonify({"success": False, "error": "Chave invalida (401 Unauthorized)."})
        return jsonify({"success": False, "error": f"Erro HTTP {e.code} ao validar chave."})
    except Exception as e:
        return jsonify({"success": False, "error": f"Erro ao validar: {str(e)[:200]}"})


@app.route("/api/setup", methods=["POST"])
def setup():
    if is_setup_done():
        return jsonify({"success": False, "error": "Setup ja foi realizado."})

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "Dados invalidos."})

    anthropic_key = data.get("anthropic_key", "").strip()
    openai_key = data.get("openai_key", "").strip()
    openrouter_key = data.get("openrouter_key", "").strip()
    telegram_token = data.get("telegram_token", "").strip()
    selected_model = data.get("selected_model", "").strip()

    # Validar que pelo menos uma API key foi fornecida
    if not anthropic_key and not openai_key and not openrouter_key:
        return jsonify({"success": False, "error": "Forneca pelo menos uma chave de API."})
    if anthropic_key and not re.match(r"^sk-ant-", anthropic_key):
        return jsonify({"success": False, "error": "Anthropic API Key deve comecar com sk-ant-"})

    # Validar Telegram token
    if not telegram_token or ":" not in telegram_token:
        return jsonify({"success": False, "error": "Telegram Bot Token invalido."})

    token = read_token()

    # Salvar API keys no .env
    if anthropic_key:
        update_env("ANTHROPIC_API_KEY", anthropic_key)
    if openai_key:
        update_env("OPENAI_API_KEY", openai_key)
    if openrouter_key:
        update_env("OPENROUTER_API_KEY", openrouter_key)
    update_env("TELEGRAM_BOT_TOKEN", telegram_token)

    # Garantir que toda a estrutura de diretorios existe com permissoes corretas (UID 1000 = node no container)
    for d in [OPENCLAW_CONFIG_DIR, AGENT_DIR, f"{OPENCLAW_CONFIG_DIR}/workspace"]:
        os.makedirs(d, exist_ok=True)
    subprocess.run(["chown", "-R", "1000:1000", OPENCLAW_CONFIG_DIR], capture_output=True)

    # Limpar channels do openclaw.json antes do onboard (evita validacao com valores antigos)
    pre_config_path = os.path.join(OPENCLAW_CONFIG_DIR, "openclaw.json")
    if os.path.exists(pre_config_path):
        try:
            with open(pre_config_path, "r") as f:
                pre_config = json.load(f)
            if "channels" in pre_config:
                del pre_config["channels"]
                with open(pre_config_path, "w") as f:
                    json.dump(pre_config, f, indent=2)
        except Exception:
            pass

    # Rodar onboard oficial do OpenClaw
    try:
        onboard_cmd = [
            "docker", "compose", "-f", f"{OPENCLAW_DIR}/docker-compose.yml",
            "run", "--rm",
        ]
        # Passar chaves disponiveis como env vars para o onboard
        if anthropic_key:
            onboard_cmd += ["-e", f"ANTHROPIC_API_KEY={anthropic_key}"]
        if openai_key:
            onboard_cmd += ["-e", f"OPENAI_API_KEY={openai_key}"]
        if openrouter_key:
            onboard_cmd += ["-e", f"OPENROUTER_API_KEY={openrouter_key}"]
        onboard_cmd += [
            "openclaw-cli", "onboard",
                "--non-interactive", "--accept-risk",
                "--mode", "local",
                "--flow", "quickstart",
                "--gateway-bind", "lan",
                "--gateway-auth", "token",
                "--skip-channels",
                "--skip-skills",
                "--skip-health",
                "--no-install-daemon",
            ]
        onboard_result = subprocess.run(
            onboard_cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=OPENCLAW_DIR,
        )
        if onboard_result.returncode != 0:
            return jsonify({
                "success": False,
                "error": f"Onboard falhou: {onboard_result.stderr[:500]}"
            })
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "Timeout no onboard (120s)."})
    except Exception as e:
        return jsonify({"success": False, "error": f"Erro no onboard: {e}"})

    # Aguardar sync do filesystem
    time.sleep(3)
    subprocess.run(["sync"], capture_output=True)

    # Ler openclaw.json gerado pelo onboard
    config_path = os.path.join(OPENCLAW_CONFIG_DIR, "openclaw.json")
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except Exception as e:
        return jsonify({"success": False, "error": f"Erro ao ler openclaw.json: {e}"})

    # Capturar token gerado pelo onboard
    onboard_token = (config.get("gateway", {}).get("auth", {}).get("token") or "").strip()
    if onboard_token:
        token = onboard_token
        with open(TOKEN_FILE, "w") as f:
            f.write(token)
        os.chmod(TOKEN_FILE, 0o600)
        update_env("OPENCLAW_GATEWAY_TOKEN", token)

    # Garantir dangerouslyDisableDeviceAuth e origin fallback para acesso LAN
    config.setdefault("gateway", {})
    config["gateway"].setdefault("controlUi", {})
    config["gateway"]["controlUi"]["dangerouslyDisableDeviceAuth"] = True
    config["gateway"]["controlUi"]["dangerouslyAllowHostHeaderOriginFallback"] = True

    # Salvar modelo selecionado pelo usuario
    if selected_model:
        config.setdefault("agents", {}).setdefault("defaults", {})
        config["agents"]["defaults"]["model"] = {"primary": selected_model}

    try:
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        return jsonify({"success": False, "error": f"Erro ao salvar openclaw.json: {e}"})

    # Criar auth-profiles.json
    os.makedirs(AGENT_DIR, exist_ok=True)
    profiles = {}
    order = {}
    if anthropic_key:
        profiles["anthropic:default"] = {
            "type": "api_key",
            "provider": "anthropic",
            "key": anthropic_key,
        }
        order["anthropic"] = ["anthropic:default"]
    if openai_key:
        profiles["openai:default"] = {
            "type": "api_key",
            "provider": "openai",
            "key": openai_key,
        }
        order["openai"] = ["openai:default"]
    if openrouter_key:
        profiles["openrouter:default"] = {
            "type": "api_key",
            "provider": "openrouter",
            "key": openrouter_key,
        }
        order["openrouter"] = ["openrouter:default"]
    auth_profiles = {
        "version": 1,
        "profiles": profiles,
        "order": order,
    }
    auth_profiles_path = os.path.join(AGENT_DIR, "auth-profiles.json")
    with open(auth_profiles_path, "w") as f:
        json.dump(auth_profiles, f, indent=2)
    os.chmod(auth_profiles_path, 0o600)

    # Gerar arquivos de persona (.md) no workspace
    persona = data.get("persona", {})
    if persona:
        try:
            write_persona_files(persona)
        except Exception:
            pass  # Nao falhar o setup por causa da persona

    # Permissoes (UID 1000 = node no container)
    subprocess.run(["chown", "-R", "1000:1000", OPENCLAW_CONFIG_DIR], capture_output=True)

    # Configurar acesso Docker (socket + cron) antes de subir o gateway
    try:
        setup_docker_access()
    except Exception:
        pass  # Nao falhar o setup por causa disso

    # Iniciar OpenClaw Gateway
    try:
        result = subprocess.run(
            ["docker", "compose", "-f", f"{OPENCLAW_DIR}/docker-compose.yml", "up", "-d", "openclaw-gateway"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=OPENCLAW_DIR,
        )
        if result.returncode != 0:
            return jsonify({
                "success": False,
                "error": f"Falha ao iniciar gateway: {result.stderr[:500]}"
            })
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "Timeout ao iniciar gateway (120s)."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

    # Aguardar gateway ficar online (health check)
    import urllib.request
    gateway_url = f"http://127.0.0.1:18789/?token={token}"
    for attempt in range(30):  # max 60 segundos
        try:
            req = urllib.request.urlopen(gateway_url, timeout=2)
            if req.getcode() == 200:
                break
        except Exception:
            pass
        time.sleep(2)

    # Injetar Telegram DEPOIS do gateway estar online (hot-reload)
    if telegram_token:
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            config.setdefault("channels", {})
            config["channels"]["telegram"] = {
                "enabled": True,
                "botToken": telegram_token,
                "dmPolicy": "pairing",
            }
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)
            subprocess.run(["chown", "1000:1000", config_path], capture_output=True)
            # Reiniciar gateway para carregar config do Telegram (hot-reload nao e confiavel)
            subprocess.run(
                ["docker", "compose", "-f", f"{OPENCLAW_DIR}/docker-compose.yml",
                 "restart", "openclaw-gateway"],
                capture_output=True, text=True, timeout=60, cwd=OPENCLAW_DIR,
            )
            # Aguardar gateway reiniciar com Telegram provider
            time.sleep(8)
        except Exception as e:
            # Nao falhar o setup por causa do Telegram
            pass

    server_ip = get_server_ip()
    url = f"http://{server_ip}:18789/?token={token}"

    # NAO marcar setup-done aqui — aguardar pairing ser confirmado
    return jsonify({"success": True, "url": url, "token": token})


@app.route("/api/pairing", methods=["POST"])
def pairing():
    """Aprovar pareamento do Telegram."""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "Dados invalidos."})

    code = data.get("code", "").strip().upper()
    if not code or len(code) < 4:
        return jsonify({"success": False, "error": "Codigo invalido."})

    try:
        result = subprocess.run(
            [
                "docker", "compose", "-f", f"{OPENCLAW_DIR}/docker-compose.yml",
                "exec", "-T", "openclaw-gateway",
                "node", "dist/index.js", "pairing", "approve", "telegram", code,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=OPENCLAW_DIR,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            stdout = result.stdout.strip()
            error_msg = stderr or stdout or "Codigo nao encontrado ou expirado."
            return jsonify({"success": False, "error": error_msg[:300]})
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "Timeout ao processar pareamento."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

    finalize_setup()
    return jsonify({"success": True})


@app.route("/api/skip-pairing", methods=["POST"])
def skip_pairing():
    """Pular pairing e finalizar setup."""
    finalize_setup()
    return jsonify({"success": True})


def finalize_setup():
    """Marcar setup como concluido, ativar Nginx e desabilitar wizard."""
    with open(SETUP_DONE_FILE, "w") as f:
        f.write("done")

    # Ativar symlink do Nginx
    nginx_available = "/etc/nginx/sites-available/openclaw"
    nginx_enabled = "/etc/nginx/sites-enabled/openclaw"
    if os.path.exists(nginx_available) and not os.path.exists(nginx_enabled):
        try:
            os.symlink(nginx_available, nginx_enabled)
        except Exception:
            pass

    # Criar script de transicao e executar via systemd-run (processo independente)
    # Precisa ser independente pois systemctl stop mata o proprio processo Gunicorn
    switch_script = "/tmp/openclaw-switch-to-nginx.sh"
    with open(switch_script, "w") as f:
        f.write("#!/bin/bash\n")
        f.write("sleep 3\n")
        f.write("systemctl disable openclaw-setup-web\n")
        f.write("systemctl stop openclaw-setup-web\n")
        f.write("sleep 2\n")
        f.write("systemctl enable --now nginx\n")
    os.chmod(switch_script, 0o755)
    subprocess.Popen(
        ["systemd-run", "--scope", "--quiet", switch_script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
