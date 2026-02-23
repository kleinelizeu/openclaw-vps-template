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

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: #0a0a0a;
            color: #f5f5f5;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 16px;
        }

        .wizard {
            max-width: 560px;
            width: 100%;
        }

        /* Progress bar */
        .progress {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0;
            margin-bottom: 32px;
            padding: 0 20px;
        }
        .progress-dot {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            background: #2a2a2a;
            border: 2px solid #3a3a3a;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 13px;
            font-weight: 600;
            color: #666;
            transition: all 0.3s;
            flex-shrink: 0;
        }
        .progress-dot.active {
            background: #dc2626;
            border-color: #dc2626;
            color: white;
        }
        .progress-dot.done {
            background: #22c55e;
            border-color: #22c55e;
            color: white;
        }
        .progress-line {
            height: 2px;
            flex: 1;
            background: #2a2a2a;
            transition: background 0.3s;
        }
        .progress-line.done {
            background: #22c55e;
        }

        /* Card container */
        .card {
            background: #141414;
            border: 1px solid #2a2a2a;
            border-radius: 16px;
            padding: 36px;
            position: relative;
            min-height: 400px;
        }

        /* Steps */
        .step {
            display: none;
            animation: fadeIn 0.3s ease;
        }
        .step.active { display: block; }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Typography */
        h2 {
            font-family: 'Syne', 'Inter', sans-serif;
            font-size: 22px;
            font-weight: 700;
            margin-bottom: 8px;
            color: #f5f5f5;
        }
        .subtitle {
            font-family: 'Space Grotesk', 'Inter', sans-serif;
            color: #a3a3a3;
            font-size: 14px;
            line-height: 1.5;
            margin-bottom: 24px;
        }

        /* Hero step */
        .hero-text { text-align: center; }
        .hero-text h1 {
            font-family: 'Syne', sans-serif;
            font-size: 28px;
            font-weight: 800;
            line-height: 1.2;
            margin-bottom: 8px;
        }
        .hero-text h1 .red { color: #dc2626; }
        .hero-text h1 .purple { color: #7c3aed; }
        .hero-brand {
            font-size: 12px;
            color: #666;
            margin-top: 16px;
            letter-spacing: 0.05em;
        }
        .hero-brand span { color: #a3a3a3; }

        /* Channel cards */
        .channel-grid {
            display: flex;
            gap: 12px;
            margin-bottom: 16px;
        }
        .channel-card {
            flex: 1;
            padding: 16px 12px;
            border-radius: 12px;
            border: 2px solid #2a2a2a;
            background: #1a1a1a;
            text-align: center;
            cursor: pointer;
            transition: all 0.2s;
            position: relative;
        }
        .channel-card:hover:not(.disabled) {
            border-color: #dc2626;
            background: #1f1f1f;
            transform: translateY(-2px);
        }
        .channel-card.selected {
            border-color: #dc2626;
            background: rgba(220, 38, 38, 0.08);
        }
        .channel-card.disabled {
            opacity: 0.4;
            cursor: not-allowed;
        }
        .channel-icon {
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 8px;
        }
        .channel-icon svg {
            width: 32px;
            height: 32px;
            fill: #f5f5f5;
            transition: fill 0.2s;
        }
        .channel-card.disabled .channel-icon svg {
            fill: #666;
        }
        .channel-name {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 13px;
            font-weight: 600;
        }
        .channel-badge {
            position: absolute;
            top: 8px;
            right: 8px;
            background: #2a2a2a;
            color: #666;
            font-size: 9px;
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 4px;
            text-transform: uppercase;
        }
        .channel-card.selected .channel-check {
            display: block;
        }
        .channel-check {
            display: none;
            position: absolute;
            top: 8px;
            left: 8px;
            background: #dc2626;
            color: white;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            font-size: 12px;
            line-height: 20px;
        }

        /* Form elements */
        .form-group {
            margin-bottom: 20px;
        }
        .form-group label {
            display: block;
            font-family: 'Space Grotesk', sans-serif;
            font-size: 13px;
            font-weight: 600;
            color: #d4d4d4;
            margin-bottom: 6px;
        }
        .form-group .hint {
            font-size: 12px;
            color: #737373;
            margin-bottom: 8px;
            line-height: 1.4;
        }
        .form-group .hint a {
            color: #dc2626;
            text-decoration: none;
        }
        .form-group .hint a:hover { text-decoration: underline; }
        .form-group input {
            width: 100%;
            padding: 12px 14px;
            background: #0a0a0a;
            border: 1px solid #2a2a2a;
            border-radius: 10px;
            color: #f5f5f5;
            font-size: 14px;
            font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
            transition: border-color 0.2s;
        }
        .form-group input:focus {
            outline: none;
            border-color: #dc2626;
        }
        .form-group input::placeholder { color: #404040; }
        .form-group input.error { border-color: #dc2626; }

        /* Telegram instructions */
        .tg-steps {
            background: #0a0a0a;
            border: 1px solid #2a2a2a;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .tg-step {
            display: flex;
            gap: 12px;
            margin-bottom: 14px;
            align-items: flex-start;
        }
        .tg-step:last-child { margin-bottom: 0; }
        .tg-num {
            width: 24px;
            height: 24px;
            border-radius: 50%;
            background: #dc2626;
            color: white;
            font-size: 12px;
            font-weight: 700;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            margin-top: 1px;
        }
        .tg-text {
            font-size: 13px;
            color: #d4d4d4;
            line-height: 1.5;
        }
        .tg-text code {
            background: #1a1a1a;
            padding: 1px 6px;
            border-radius: 4px;
            font-family: monospace;
            color: #f5f5f5;
            font-size: 12px;
        }

        .tg-open-btn {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 10px 20px;
            background: #0088cc;
            border: none;
            border-radius: 8px;
            color: white;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            text-decoration: none;
            transition: opacity 0.2s;
            margin-bottom: 20px;
        }
        .tg-open-btn:hover { opacity: 0.85; }

        /* Buttons */
        .btn-row {
            display: flex;
            gap: 12px;
            margin-top: 24px;
        }
        .btn {
            flex: 1;
            padding: 14px;
            border-radius: 10px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            border: none;
            transition: all 0.2s;
            font-family: 'Space Grotesk', 'Inter', sans-serif;
        }
        .btn-back {
            background: #1a1a1a;
            color: #a3a3a3;
            border: 1px solid #2a2a2a;
        }
        .btn-back:hover { background: #222; color: #f5f5f5; }
        .btn-next {
            background: #dc2626;
            color: white;
        }
        .btn-next:hover { background: #b91c1c; }
        .btn-next:disabled {
            opacity: 0.4;
            cursor: not-allowed;
        }
        .btn-full {
            width: 100%;
            padding: 16px;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            border: none;
            background: #dc2626;
            color: white;
            font-family: 'Space Grotesk', 'Inter', sans-serif;
            transition: background 0.2s;
            margin-top: 24px;
        }
        .btn-full:hover { background: #b91c1c; }

        /* Loading step */
        .loading-steps {
            text-align: center;
            padding: 40px 0;
        }
        .spinner {
            width: 48px;
            height: 48px;
            border: 3px solid #2a2a2a;
            border-top-color: #dc2626;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin: 0 auto 24px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .loading-msg {
            font-size: 15px;
            color: #a3a3a3;
            transition: opacity 0.3s;
        }

        /* Pairing notice */
        .pairing-notice {
            display: flex;
            align-items: center;
            gap: 10px;
            background: #1e1e1e;
            border: 1px solid #dc2626;
            border-radius: 10px;
            padding: 12px 16px;
            margin-bottom: 16px;
            font-size: 13px;
            color: #d4d4d4;
        }
        .pairing-notice.ready {
            border-color: #22c55e;
            background: #0a1a0a;
        }
        .spinner-small {
            width: 20px;
            height: 20px;
            border: 2px solid #2a2a2a;
            border-top-color: #dc2626;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            flex-shrink: 0;
        }

        /* Pairing step */
        .pairing-input {
            display: flex;
            gap: 8px;
            margin-top: 16px;
        }
        .pairing-input input {
            flex: 1;
            padding: 14px;
            background: #0a0a0a;
            border: 2px solid #2a2a2a;
            border-radius: 10px;
            color: #f5f5f5;
            font-size: 20px;
            font-family: monospace;
            text-align: center;
            letter-spacing: 4px;
            text-transform: uppercase;
        }
        .pairing-input input:focus {
            outline: none;
            border-color: #dc2626;
        }

        /* Success step */
        .success-icon {
            width: 64px;
            height: 64px;
            border-radius: 50%;
            background: rgba(34, 197, 94, 0.15);
            border: 2px solid #22c55e;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 28px;
            margin: 0 auto 20px;
        }
        .success-link {
            display: inline-block;
            padding: 14px 32px;
            background: #dc2626;
            border-radius: 10px;
            color: white;
            text-decoration: none;
            font-size: 15px;
            font-weight: 600;
            margin-top: 16px;
            transition: background 0.2s;
        }
        .success-link:hover { background: #b91c1c; }
        .success-tip {
            margin-top: 20px;
            padding: 14px;
            background: #0a0a0a;
            border: 1px solid #2a2a2a;
            border-radius: 10px;
            font-size: 13px;
            color: #a3a3a3;
            line-height: 1.5;
        }

        /* Status messages */
        .status-msg {
            padding: 10px 14px;
            border-radius: 8px;
            font-size: 13px;
            margin-top: 12px;
            display: none;
        }
        .status-msg.error {
            display: block;
            background: rgba(220, 38, 38, 0.1);
            border: 1px solid #dc2626;
            color: #fca5a5;
        }
        .status-msg.info {
            display: block;
            background: rgba(124, 58, 237, 0.1);
            border: 1px solid #7c3aed;
            color: #c4b5fd;
        }

        /* Key validation + model select */
        .key-row { display: flex; gap: 8px; align-items: center; }
        .key-row input { flex: 1; }
        .validate-btn {
            padding: 12px 16px;
            background: #1a1a1a;
            border: 1px solid #2a2a2a;
            border-radius: 10px;
            color: #a3a3a3;
            font-family: 'Space Grotesk', sans-serif;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            white-space: nowrap;
            transition: all 0.2s;
        }
        .validate-btn:hover { background: #222; color: #f5f5f5; }
        .validate-btn.loading { opacity: 0.5; pointer-events: none; }
        .validate-btn.valid { background: rgba(34,197,94,0.1); border-color: #22c55e; color: #22c55e; }
        .key-status { font-size: 12px; margin-top: 4px; }
        .key-status.valid { color: #22c55e; }
        .key-status.invalid { color: #dc2626; }
        .model-select-wrap { margin-top: 8px; display: none; }
        .model-select-wrap.visible { display: block; }
        .model-select-wrap label { margin-bottom: 4px; }
        .model-select {
            width: 100%;
            padding: 10px 12px;
            background: #0a0a0a;
            border: 1px solid #2a2a2a;
            border-radius: 8px;
            color: #f5f5f5;
            font-size: 13px;
            font-family: 'Inter', sans-serif;
            appearance: none;
            -webkit-appearance: none;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23666' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-position: right 12px center;
            padding-right: 32px;
        }
        .model-select:focus { outline: none; border-color: #dc2626; }

        /* Responsive */
        @media (max-width: 480px) {
            .card { padding: 24px 20px; }
            .channel-grid { flex-direction: column; }
            h2 { font-size: 20px; }
            .hero-text h1 { font-size: 24px; }
        }
    </style>
</head>
<body>
    <div class="wizard">
        <!-- Progress Bar -->
        <div class="progress" id="progressBar">
            <div class="progress-dot active" id="dot1">1</div>
            <div class="progress-line" id="line1"></div>
            <div class="progress-dot" id="dot2">2</div>
            <div class="progress-line" id="line2"></div>
            <div class="progress-dot" id="dot3">3</div>
            <div class="progress-line" id="line3"></div>
            <div class="progress-dot" id="dot4">4</div>
            <div class="progress-line" id="line4"></div>
            <div class="progress-dot" id="dot5">5</div>
        </div>

        <div class="card">
            <!-- Step 1: Hero -->
            <div class="step active" id="step1" style="background:linear-gradient(135deg, rgba(220,38,38,0.04), rgba(124,58,237,0.04));border-radius:12px;padding:8px;">
                <div class="hero-text">
                    <div style="display:flex;align-items:center;justify-content:center;gap:16px;margin-bottom:24px;">
                        <img src="https://upload.wikimedia.org/wikipedia/commons/5/5e/Openclaw-logo-text-dark.png"
                             alt="OpenClaw" style="height:44px;" />
                        <span style="color:#3a3a3a;font-size:24px;font-weight:300;">+</span>
                        <img src="https://lurahosting.com.br/images/logo.png"
                             alt="Lura Hosting" style="height:44px;" />
                    </div>
                    <h1>Comunidade <span class="red">Claw</span> Brasil<br>+ <span class="purple">Lura</span> Hosting</h1>
                    <p class="subtitle" style="margin-top:12px;">
                        Configure seu assistente pessoal de IA<br>em poucos minutos.
                    </p>
                    <button class="btn-full" onclick="goTo(2)">
                        Configurar meu OpenClaw &rarr;
                    </button>
                    <p class="hero-brand">Powered by <span>bisnishub</span></p>
                </div>
            </div>

            <!-- Step 2: Escolher Canal -->
            <div class="step" id="step2">
                <h2>Escolha o canal</h2>
                <p class="subtitle">Onde seu assistente de IA vai responder?</p>

                <div class="channel-grid">
                    <div class="channel-card selected" id="ch-telegram" onclick="selectChannel('telegram')">
                        <div class="channel-check">&#10003;</div>
                        <div class="channel-icon">
                            <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.479.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/></svg>
                        </div>
                        <div class="channel-name">Telegram</div>
                    </div>
                    <div class="channel-card disabled">
                        <div class="channel-badge">Em breve</div>
                        <div class="channel-icon">
                            <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 0 1-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 0 1-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 0 1 2.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0 0 12.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 0 0 5.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 0 0-3.48-8.413z"/></svg>
                        </div>
                        <div class="channel-name">WhatsApp</div>
                    </div>
                    <div class="channel-card disabled">
                        <div class="channel-badge">Em breve</div>
                        <div class="channel-icon">
                            <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.095 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.095 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/></svg>
                        </div>
                        <div class="channel-name">Discord</div>
                    </div>
                </div>

                <div class="btn-row">
                    <button class="btn btn-back" onclick="goTo(1)">Voltar</button>
                    <button class="btn btn-next" onclick="goTo(3)">Proximo &rarr;</button>
                </div>
            </div>

            <!-- Step 3: API Keys -->
            <div class="step" id="step3">
                <h2>Chaves de API</h2>
                <p class="subtitle">Insira pelo menos a chave da Anthropic e valide para escolher o modelo. As demais sao opcionais.</p>

                <div class="form-group">
                    <label>Anthropic API Key *</label>
                    <p class="hint">
                        Obtenha em <a href="https://console.anthropic.com" target="_blank">console.anthropic.com</a><br>
                        <a href="#" target="_blank" style="color:#7c3aed;">Se voce nao sabe como criar sua chave, assista ao video tutorial</a>
                    </p>
                    <div class="key-row">
                        <input type="text" id="anthropic_key"
                               placeholder="sk-ant-api03-..."
                               autocomplete="off" spellcheck="false">
                        <button type="button" class="validate-btn" id="anthropic_validate" onclick="validateKey('anthropic')">Validar</button>
                    </div>
                    <div class="key-status" id="anthropic_status"></div>
                    <div class="model-select-wrap" id="anthropic_model_wrap">
                        <label>Modelo</label>
                        <select class="model-select" id="anthropic_model"></select>
                    </div>
                </div>

                <div class="form-group">
                    <label>OpenAI API Key <span style="color:#737373;font-weight:400;">(opcional)</span></label>
                    <p class="hint">
                        Obtenha em <a href="https://platform.openai.com/api-keys" target="_blank">platform.openai.com</a>
                    </p>
                    <div class="key-row">
                        <input type="text" id="openai_key"
                               placeholder="sk-..."
                               autocomplete="off" spellcheck="false">
                        <button type="button" class="validate-btn" id="openai_validate" onclick="validateKey('openai')" style="display:none;">Validar</button>
                    </div>
                    <div class="key-status" id="openai_status"></div>
                    <div class="model-select-wrap" id="openai_model_wrap">
                        <label>Modelo</label>
                        <select class="model-select" id="openai_model"></select>
                    </div>
                </div>

                <div class="form-group">
                    <label>OpenRouter API Key <span style="color:#737373;font-weight:400;">(opcional)</span></label>
                    <p class="hint">
                        Obtenha em <a href="https://openrouter.ai/keys" target="_blank">openrouter.ai</a>
                    </p>
                    <div class="key-row">
                        <input type="text" id="openrouter_key"
                               placeholder="sk-or-v1-..."
                               autocomplete="off" spellcheck="false">
                        <button type="button" class="validate-btn" id="openrouter_validate" onclick="validateKey('openrouter')" style="display:none;">Validar</button>
                    </div>
                    <div class="key-status" id="openrouter_status"></div>
                    <div class="model-select-wrap" id="openrouter_model_wrap">
                        <label>Modelo</label>
                        <select class="model-select" id="openrouter_model"></select>
                    </div>
                </div>

                <div id="step3Error" class="status-msg"></div>

                <div class="btn-row">
                    <button class="btn btn-back" onclick="goTo(2)">Voltar</button>
                    <button class="btn btn-next" id="step3Next" onclick="validateStep3()">Proximo &rarr;</button>
                </div>
            </div>

            <!-- Step 4: Telegram Bot -->
            <div class="step" id="step4">
                <h2>Criar Bot no Telegram</h2>
                <p class="subtitle">Siga as instrucoes abaixo para criar seu bot.</p>

                <div class="tg-steps">
                    <div class="tg-step">
                        <div class="tg-num">1</div>
                        <div class="tg-text">Abra o Telegram e busque <code>BotFather</code> (bot oficial com selo azul)</div>
                    </div>
                    <div class="tg-step">
                        <div class="tg-num">2</div>
                        <div class="tg-text">Inicie o chat e envie o comando <code>/newbot</code></div>
                    </div>
                    <div class="tg-step">
                        <div class="tg-num">3</div>
                        <div class="tg-text">Siga as instrucoes para dar um <strong>nome</strong> e <strong>username</strong> ao seu bot</div>
                    </div>
                    <div class="tg-step">
                        <div class="tg-num">4</div>
                        <div class="tg-text">O BotFather enviara um <strong>token</strong> (sequencia longa de numeros e letras). <strong>Copie-o.</strong></div>
                    </div>
                </div>

                <a href="https://t.me/BotFather" target="_blank" class="tg-open-btn">
                    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" style="width:16px;height:16px;fill:white;flex-shrink:0;"><path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.479.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/></svg>
                    Abrir BotFather no Telegram
                </a>

                <div class="form-group">
                    <label>Bot Token *</label>
                    <p class="hint">Cole o token que o BotFather enviou</p>
                    <input type="text" id="telegram_token"
                           placeholder="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
                           autocomplete="off" spellcheck="false">
                </div>

                <div id="step4Error" class="status-msg"></div>

                <div class="btn-row">
                    <button class="btn btn-back" onclick="goTo(3)">Voltar</button>
                    <button class="btn btn-next" onclick="validateStep4()">Implantar &rarr;</button>
                </div>
            </div>

            <!-- Step 5: Loading/Deploy -->
            <div class="step" id="step5">
                <div class="loading-steps">
                    <div class="spinner"></div>
                    <div class="loading-msg" id="loadingMsg">Configurando sua instancia...</div>
                </div>
                <div id="step5Error" class="status-msg"></div>
            </div>

            <!-- Step 6: Pairing (shown after step5 finishes, uses dot5) -->
            <div class="step" id="step6">
                <h2>Conectar seu Telegram</h2>
                <p class="subtitle">Seu bot esta ativo! Agora vamos conectar voce para que somente voce possa conversar com ele.</p>

                <div class="tg-steps">
                    <div class="tg-step">
                        <div class="tg-num">1</div>
                        <div class="tg-text">Abra o Telegram e busque pelo nome do seu bot</div>
                    </div>
                    <div class="tg-step">
                        <div class="tg-num">2</div>
                        <div class="tg-text">Clique em <strong>Iniciar</strong> (ou envie <strong>/start</strong>)</div>
                    </div>
                    <div class="tg-step">
                        <div class="tg-num">3</div>
                        <div class="tg-text">Envie qualquer mensagem (ex: <strong>oi</strong>)</div>
                    </div>
                    <div class="tg-step">
                        <div class="tg-num">4</div>
                        <div class="tg-text">O bot vai responder com um <strong>codigo de 8 caracteres</strong></div>
                    </div>
                    <div class="tg-step">
                        <div class="tg-num">5</div>
                        <div class="tg-text">Digite o codigo abaixo para liberar o acesso</div>
                    </div>
                </div>

                <div class="pairing-notice" id="pairingNotice">
                    <div class="spinner-small"></div>
                    <span>Aguarde <strong id="pairingCountdown">15</strong>s para o bot ficar online no Telegram...</span>
                </div>

                <div class="pairing-input" id="pairingInputArea" style="opacity:0.4;pointer-events:none;">
                    <input type="text" id="pairing_code" maxlength="8"
                           placeholder="ABCD1234" autocomplete="off"
                           style="text-transform:uppercase;letter-spacing:4px;text-align:center;font-size:20px;">
                </div>

                <div id="step6Error" class="status-msg"></div>
                <div id="step6Info" class="status-msg"></div>

                <button class="btn-full" id="pairingBtn" onclick="submitPairing()" disabled>
                    Confirmar Pareamento
                </button>

                <div id="pairingRetry" style="display:none;text-align:center;margin-top:12px;">
                    <p style="color:#a3a3a3;font-size:13px;margin-bottom:8px;">
                        Nao recebeu o codigo? Envie outra mensagem para o bot e aguarde alguns segundos.
                    </p>
                </div>

                <p style="text-align:center;margin-top:12px;">
                    <a href="#" onclick="skipPairing()" style="color:#737373;font-size:12px;text-decoration:none;">
                        Pular esta etapa (configurar depois)
                    </a>
                </p>
            </div>

            <!-- Step 7: Success -->
            <div class="step" id="step7">
                <div style="text-align:center;">
                    <div class="success-icon">&#10003;</div>
                    <h2>Tudo pronto!</h2>
                    <p class="subtitle">Seu OpenClaw esta configurado e funcionando no Telegram!</p>

                    <p style="font-size:14px;color:#d4d4d4;margin-bottom:8px;line-height:1.6;">
                        O OpenClaw agora so responde a <strong>voce</strong>. Basta conversar com seu bot no Telegram para usar seu agente de IA.
                    </p>

                    <p style="font-size:13px;color:#a3a3a3;margin-bottom:20px;line-height:1.6;">
                        Voce pode acessar o Dashboard do seu OpenClaw atraves do link abaixo, mas todas as configuracoes podem ser realizadas direto pelo Telegram conversando com o seu agente OpenClaw.
                    </p>

                    <a id="dashboardLink" href="#" class="success-link" target="_blank">
                        Acessar Dashboard &rarr;
                    </a>

                    <div class="success-tip">
                        <strong>Dica:</strong> Pelo Telegram voce pode configurar skills, prompts, modelos e muito mais. Basta pedir ao seu agente!
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentStep = 1;
        const totalDots = 5;
        let setupData = {};

        function goTo(step) {
            document.getElementById('step' + currentStep).classList.remove('active');
            currentStep = step;
            document.getElementById('step' + currentStep).classList.add('active');
            updateProgress();
        }

        function updateProgress() {
            for (let i = 1; i <= totalDots; i++) {
                const dot = document.getElementById('dot' + i);
                const line = document.getElementById('line' + (i - 1));
                dot.classList.remove('active', 'done');
                if (line) line.classList.remove('done');

                if (i < getProgressDot()) {
                    dot.classList.add('done');
                    dot.innerHTML = '&#10003;';
                    if (line) line.classList.add('done');
                } else if (i === getProgressDot()) {
                    dot.classList.add('active');
                    dot.textContent = i;
                } else {
                    dot.textContent = i;
                }
            }
        }

        function getProgressDot() {
            // Map steps 1-7 to dots 1-5
            if (currentStep <= 1) return 1;
            if (currentStep <= 2) return 2;
            if (currentStep <= 3) return 3;
            if (currentStep <= 4) return 4;
            return 5; // steps 5,6,7 all use dot 5
        }

        function selectChannel(ch) {
            // Only telegram is selectable for now
        }

        // Mostrar botao Validar quando digita
        ['openai', 'openrouter'].forEach(p => {
            document.getElementById(p + '_key').addEventListener('input', function() {
                const btn = document.getElementById(p + '_validate');
                btn.style.display = this.value.trim() ? 'block' : 'none';
                // Esconder modelo se chave mudou
                document.getElementById(p + '_model_wrap').classList.remove('visible');
                document.getElementById(p + '_status').textContent = '';
                document.getElementById(p + '_validate').classList.remove('valid');
            });
        });
        document.getElementById('anthropic_key').addEventListener('input', function() {
            document.getElementById('anthropic_model_wrap').classList.remove('visible');
            document.getElementById('anthropic_status').textContent = '';
            document.getElementById('anthropic_validate').classList.remove('valid');
        });

        let validatedProviders = {};

        async function validateKey(provider) {
            const keyEl = document.getElementById(provider + '_key');
            const btn = document.getElementById(provider + '_validate');
            const statusEl = document.getElementById(provider + '_status');
            const modelWrap = document.getElementById(provider + '_model_wrap');
            const modelSelect = document.getElementById(provider + '_model');
            const key = keyEl.value.trim();

            if (!key) { statusEl.className = 'key-status invalid'; statusEl.textContent = 'Insira a chave primeiro.'; return; }

            btn.classList.add('loading');
            btn.textContent = 'Validando...';
            statusEl.textContent = '';
            modelWrap.classList.remove('visible');

            try {
                const resp = await fetch('/api/validate-key', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ provider, key })
                });
                const data = await resp.json();

                if (data.success && data.models && data.models.length > 0) {
                    statusEl.className = 'key-status valid';
                    statusEl.innerHTML = '&#10003; Chave valida — ' + data.models.length + ' modelos encontrados';
                    btn.classList.add('valid');
                    btn.textContent = '&#10003;';

                    modelSelect.innerHTML = '';
                    data.models.forEach(m => {
                        const opt = document.createElement('option');
                        opt.value = provider + '/' + m.id;
                        opt.textContent = m.name || m.id;
                        modelSelect.appendChild(opt);
                    });
                    modelWrap.classList.add('visible');
                    validatedProviders[provider] = true;
                } else {
                    statusEl.className = 'key-status invalid';
                    statusEl.textContent = data.error || 'Chave invalida ou sem modelos disponiveis.';
                    btn.classList.remove('valid');
                    btn.textContent = 'Validar';
                    validatedProviders[provider] = false;
                }
            } catch (err) {
                statusEl.className = 'key-status invalid';
                statusEl.textContent = 'Erro de conexao: ' + err.message;
                btn.textContent = 'Validar';
            }
            btn.classList.remove('loading');
        }

        function validateStep3() {
            const anthropicKey = document.getElementById('anthropic_key').value.trim();
            const openaiKey = document.getElementById('openai_key').value.trim();
            const openrouterKey = document.getElementById('openrouter_key').value.trim();
            const errEl = document.getElementById('step3Error');

            // Validar formato se preenchido
            if (anthropicKey && !anthropicKey.startsWith('sk-ant-')) {
                errEl.className = 'status-msg error';
                errEl.textContent = 'A chave da Anthropic deve comecar com sk-ant-';
                return;
            }

            // Pelo menos uma chave deve estar preenchida e validada
            const hasAny = (anthropicKey && validatedProviders['anthropic'])
                        || (openaiKey && validatedProviders['openai'])
                        || (openrouterKey && validatedProviders['openrouter']);
            if (!hasAny) {
                errEl.className = 'status-msg error';
                errEl.textContent = 'Insira e valide pelo menos uma chave de API.';
                return;
            }

            // Se preencheu mas nao validou, avisar
            if (anthropicKey && !validatedProviders['anthropic']) {
                errEl.className = 'status-msg error';
                errEl.textContent = 'Valide a chave da Anthropic antes de continuar.';
                return;
            }
            if (openaiKey && !validatedProviders['openai']) {
                errEl.className = 'status-msg error';
                errEl.textContent = 'Valide a chave da OpenAI antes de continuar.';
                return;
            }
            if (openrouterKey && !validatedProviders['openrouter']) {
                errEl.className = 'status-msg error';
                errEl.textContent = 'Valide a chave da OpenRouter antes de continuar.';
                return;
            }

            errEl.className = 'status-msg';
            errEl.style.display = 'none';
            goTo(4);
        }

        function validateStep4() {
            const token = document.getElementById('telegram_token').value.trim();
            const errEl = document.getElementById('step4Error');

            if (!token) {
                errEl.className = 'status-msg error';
                errEl.textContent = 'O token do bot e obrigatorio.';
                return;
            }
            if (!token.includes(':')) {
                errEl.className = 'status-msg error';
                errEl.textContent = 'Token invalido. Deve ter o formato: 1234567890:ABCdef...';
                return;
            }
            errEl.className = 'status-msg';
            errEl.style.display = 'none';
            startDeploy();
        }

        async function startDeploy() {
            goTo(5);
            const msgEl = document.getElementById('loadingMsg');
            const errEl = document.getElementById('step5Error');

            const messages = [
                'Configurando sua instancia...',
                'Instalando configuracoes do OpenClaw...',
                'Conectando bot do Telegram...',
                'Iniciando OpenClaw Gateway...'
            ];

            let msgIdx = 0;
            const msgInterval = setInterval(() => {
                msgIdx = (msgIdx + 1) % messages.length;
                msgEl.textContent = messages[msgIdx];
            }, 3000);

            try {
                const resp = await fetch('/api/setup', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        anthropic_key: document.getElementById('anthropic_key').value.trim(),
                        openai_key: document.getElementById('openai_key').value.trim(),
                        openrouter_key: document.getElementById('openrouter_key').value.trim(),
                        telegram_token: document.getElementById('telegram_token').value.trim(),
                        selected_model: document.getElementById('anthropic_model').value
                            || document.getElementById('openai_model').value
                            || document.getElementById('openrouter_model').value
                            || '',
                    })
                });

                clearInterval(msgInterval);
                const data = await resp.json();

                if (data.success) {
                    setupData = data;
                    goTo(6);
                    startPairingCountdown();
                } else {
                    errEl.className = 'status-msg error';
                    errEl.textContent = 'Erro: ' + data.error;
                }
            } catch (err) {
                clearInterval(msgInterval);
                errEl.className = 'status-msg error';
                errEl.textContent = 'Erro de conexao: ' + err.message;
            }
        }

        function startPairingCountdown() {
            const notice = document.getElementById('pairingNotice');
            const countdown = document.getElementById('pairingCountdown');
            const inputArea = document.getElementById('pairingInputArea');
            const btn = document.getElementById('pairingBtn');
            const retryHint = document.getElementById('pairingRetry');
            let seconds = 15;

            const timer = setInterval(() => {
                seconds--;
                countdown.textContent = seconds;
                if (seconds <= 0) {
                    clearInterval(timer);
                    // Enable input area
                    notice.innerHTML = '<span style="color:#22c55e;">&#10003;</span> <span>Bot online! Envie uma mensagem para o bot no Telegram e cole o codigo abaixo.</span>';
                    notice.classList.add('ready');
                    inputArea.style.opacity = '1';
                    inputArea.style.pointerEvents = 'auto';
                    btn.disabled = false;
                    retryHint.style.display = 'block';
                    document.getElementById('pairing_code').focus();
                }
            }, 1000);
        }

        async function submitPairing() {
            const code = document.getElementById('pairing_code').value.trim().toUpperCase();
            const errEl = document.getElementById('step6Error');
            const infoEl = document.getElementById('step6Info');
            const btn = document.getElementById('pairingBtn');

            if (!code || code.length < 4) {
                errEl.className = 'status-msg error';
                errEl.textContent = 'Digite o codigo de pareamento.';
                return;
            }

            btn.disabled = true;
            btn.textContent = 'Verificando...';
            errEl.className = 'status-msg';
            errEl.style.display = 'none';

            try {
                const resp = await fetch('/api/pairing', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code: code })
                });

                const data = await resp.json();

                if (data.success) {
                    showSuccess();
                } else {
                    errEl.className = 'status-msg error';
                    errEl.textContent = 'Erro: ' + data.error;
                    btn.disabled = false;
                    btn.textContent = 'Confirmar Pareamento';
                }
            } catch (err) {
                errEl.className = 'status-msg error';
                errEl.textContent = 'Erro de conexao: ' + err.message;
                btn.disabled = false;
                btn.textContent = 'Confirmar Pareamento';
            }
        }

        async function skipPairing() {
            try {
                await fetch('/api/skip-pairing', { method: 'POST' });
            } catch(e) {}
            showSuccess();
        }

        function showSuccess() {
            if (setupData.url) {
                document.getElementById('dashboardLink').href = setupData.url;
            }
            goTo(7);
        }
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
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: #0a0a0a;
            color: #f5f5f5;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: #141414;
            border: 1px solid #2a2a2a;
            border-radius: 16px;
            padding: 40px;
            max-width: 520px;
            width: 100%;
            text-align: center;
        }
        .logos {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 16px;
            margin-bottom: 24px;
        }
        .logos img { height: 36px; }
        .logos span { color: #3a3a3a; font-size: 20px; font-weight: 300; }
        h1 { font-family: 'Syne', 'Inter', sans-serif; font-size: 24px; margin-bottom: 12px; }
        h1 span { color: #22c55e; }
        p { font-family: 'Space Grotesk', 'Inter', sans-serif; color: #a3a3a3; margin-bottom: 20px; line-height: 1.5; }
        .link-btn {
            display: inline-block;
            padding: 14px 32px;
            background: #dc2626;
            border-radius: 10px;
            color: white;
            text-decoration: none;
            font-family: 'Space Grotesk', 'Inter', sans-serif;
            font-size: 15px;
            font-weight: 600;
            transition: background 0.2s;
        }
        .link-btn:hover { background: #b91c1c; }
        .token-info {
            margin-top: 20px;
            padding: 14px;
            background: #0a0a0a;
            border-radius: 8px;
            border: 1px solid #2a2a2a;
        }
        .token-info label { font-family: 'Space Grotesk', sans-serif; font-size: 11px; color: #737373; text-transform: uppercase; letter-spacing: 0.05em; }
        .token-info code { display: block; margin-top: 6px; font-family: monospace; color: #dc2626; font-size: 12px; word-break: break-all; }
        .brand { margin-top: 24px; font-size: 11px; color: #404040; }
        .brand span { color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logos">
            <img src="https://upload.wikimedia.org/wikipedia/commons/5/5e/Openclaw-logo-text-dark.png" alt="OpenClaw" />
            <span>+</span>
            <img src="https://lurahosting.com.br/images/logo.png" alt="Lura Hosting" />
        </div>
        <h1><span>&#10003;</span> OpenClaw Configurado</h1>
        <p>Seu assistente de IA esta rodando e pronto para uso.</p>
        <a href="{{ url }}" class="link-btn">Acessar OpenClaw &rarr;</a>
        <div class="token-info">
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

    # Garantir dangerouslyDisableDeviceAuth
    config.setdefault("gateway", {})
    config["gateway"].setdefault("controlUi", {})
    config["gateway"]["controlUi"]["dangerouslyDisableDeviceAuth"] = True

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

    # Permissoes (UID 1000 = node no container)
    subprocess.run(["chown", "-R", "1000:1000", OPENCLAW_CONFIG_DIR], capture_output=True)

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

    # Usar nohup + bash em background para:
    # 1. Desabilitar o wizard
    # 2. Parar o wizard (libera porta 80)
    # 3. Iniciar Nginx
    # Precisa rodar em background pois stop mata o proprio processo
    subprocess.Popen(
        ["bash", "-c",
         "sleep 2; "
         "systemctl disable openclaw-setup-web; "
         "systemctl stop openclaw-setup-web; "
         "sleep 1; "
         "systemctl enable --now nginx"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
