# OpenClaw VPS Template

Template de VPS Ubuntu 24.04 LTS com OpenClaw pre-configurado para instalacao one-click.

## Requisitos

- Ubuntu 24.04 LTS (VM limpa)
- Minimo: 4 vCPU, 4GB RAM, 20GB disco (recomendado: 6 vCPU, 8GB RAM, 60GB SSD)
- Acesso root
- Conexao com internet

## Estrutura

```
openclaw-vps-template/
├── build-template.sh              # Script master — prepara a VM como template
├── setup/
│   ├── firstboot.sh               # Roda 1x no primeiro boot (gera token, .env)
│   ├── app.py                     # Wizard web Flask para configuracao
│   └── requirements.txt           # Dependencias Python
├── systemd/
│   ├── openclaw-firstboot.service # Systemd: executa firstboot.sh
│   └── openclaw-setup-web.service # Systemd: wizard web na porta 80
├── config/
│   ├── 99-openclaw-motd           # Banner SSH com instrucoes
│   └── openclaw-nginx.conf        # Nginx reverse proxy (ativado pos-setup)
└── README.md
```

## Como Usar

### 1. Teste Local com Multipass

```bash
# Instalar Multipass
brew install multipass

# Criar VM
multipass launch 24.04 --name openclaw-test --cpus 4 --memory 4G --disk 40G

# Transferir arquivos
multipass transfer -r openclaw-vps-template/ openclaw-test:/tmp/

# Acessar a VM
multipass shell openclaw-test

# Dentro da VM:
cd /tmp/openclaw-vps-template
sudo bash build-template.sh
```

### 2. Testar o Fluxo

```bash
# Descobrir o IP da VM (no host)
multipass info openclaw-test

# No browser, acesse: http://<IP>/
# Preencha a Anthropic API Key e clique "Iniciar OpenClaw"
# Acesse: http://<IP>:18789/?token=<TOKEN>
```

### 3. Simular Novo Boot (re-testar firstboot)

```bash
# Dentro da VM:
sudo rm -f /var/lib/openclaw-firstboot-done /var/lib/openclaw-setup-done /var/lib/openclaw-token
sudo rm -f /opt/openclaw/.env
sudo docker compose -f /opt/openclaw/docker-compose.yml down 2>/dev/null
sudo systemctl restart openclaw-firstboot
sudo systemctl restart openclaw-setup-web
```

### 4. Exportar Imagem QCOW2

```bash
# Parar a VM
multipass stop openclaw-test

# Localizar disco (macOS)
ls ~/Library/Application\ Support/multipassd/qemu/vault/instances/openclaw-test/

# Converter para QCOW2
qemu-img convert -O qcow2 <disco-original> openclaw-template.qcow2
```

## Portas

| Porta | Servico | Notas |
|-------|---------|-------|
| 22    | SSH     | Sempre ativo |
| 80    | Wizard / Nginx | Wizard no primeiro acesso, Nginx apos setup |
| 18789 | OpenClaw Gateway | Porta principal do OpenClaw |
| 18790 | OpenClaw Bridge  | Servico bridge |

## Fluxo do Cliente

1. Recebe IP + senha root da VPS
2. Acessa `http://<IP>/` no navegador
3. Wizard exibe token gerado e formulario para API keys
4. Preenche Anthropic API Key (obrigatoria) e clica "Iniciar"
5. OpenClaw fica disponivel em `http://<IP>:18789/?token=<TOKEN>`

## Seguranca

- Firewall UFW ativo (apenas portas 22, 80, 18789, 18790)
- fail2ban para protecao SSH
- Wizard web se auto-desabilita apos setup
- Token gerado com `openssl rand -hex 32` (64 chars)
- Container Docker roda como usuario `node` (nao root)
- API keys armazenadas em .env com permissao 600
