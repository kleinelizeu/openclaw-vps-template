# OpenClaw VPS Template — Guia de Deploy LuraHosting

Guia completo para importar e disponibilizar o template OpenClaw no painel VirtFusion.

---

## 1. Visao Geral

Este template entrega uma VPS Ubuntu 24.04 LTS com:

| Componente | Detalhes |
|---|---|
| **OpenClaw** | Clonado em `/opt/openclaw`, imagem Docker pre-buildada (`openclaw:local`) |
| **Setup Wizard** | Interface web (Flask/Gunicorn) na porta 80, guia o usuario em 5 etapas |
| **Docker CE** | + Docker Compose v2 |
| **Nginx** | Reverse proxy para o Gateway (ativado apos setup) |
| **UFW** | Firewall configurado (22, 80, 443, 18789, 18790) |
| **fail2ban** | Protecao SSH ativa |
| **cloud-init** | Compativel com VirtFusion para injecao de hostname/SSH keys/rede |
| **qemu-guest-agent** | Para comunicacao com o hypervisor KVM |
| **Swap 1GB** | Para VPS com pouca RAM |

### Fluxo do Usuario Final

```
Criar VPS no painel → Boot → Firstboot automatico → Acessar http://IP
→ Token → API Key + Validar + Escolher Modelo → Telegram Bot → Deploy → Pronto!
```

---

## 2. Requisitos do Hypervisor

- **Hypervisor:** KVM/QEMU (VirtFusion)
- **Formato da imagem:** QCOW2 (renomeado para `.img`)
- **SO base:** Ubuntu 24.04 LTS (Noble Numbat)
- **Arquitetura:** x86_64 (amd64)
- **Firmware:** BIOS ou UEFI
- **VirtIO:** Disco e rede via VirtIO (padrao VirtFusion)

### Recursos Minimos por VPS

| Recurso | Minimo | Recomendado |
|---|---|---|
| vCPU | 1 | 2 |
| RAM | 1 GB | 2 GB |
| Disco | 15 GB | 25 GB |
| Rede | 1 interface (IPv4) | IPv4 + IPv6 |

---

## 3. Como Gerar a Imagem QCOW2

### Opcao A: A Partir de uma VM Limpa (Recomendado)

1. **Criar VM Ubuntu 24.04** no hypervisor de build (pode ser local ou no proprio KVM):
   ```bash
   # Exemplo com virt-install
   virt-install \
     --name openclaw-template \
     --ram 2048 --vcpus 2 \
     --disk size=20,format=qcow2 \
     --cdrom ubuntu-24.04-live-server-amd64.iso \
     --os-variant ubuntu24.04 \
     --network bridge=br0
   ```

2. **Instalar Ubuntu 24.04 Server** (instalacao minima, sem LVM, com OpenSSH)

3. **Clonar o repositorio e executar o build:**
   ```bash
   ssh root@IP_DA_VM
   apt-get update && apt-get install -y git
   git clone https://github.com/kleinelizeu/openclaw-vps-template.git /tmp/openclaw-template
   cd /tmp/openclaw-template
   bash build-template.sh
   ```

4. **Desligar a VM:**
   ```bash
   shutdown -h now
   ```

5. **Compactar a imagem no host:**
   ```bash
   # Localizar o disco da VM (ex: /var/lib/libvirt/images/openclaw-template.qcow2)
   qemu-img convert -c -O qcow2 \
     /var/lib/libvirt/images/openclaw-template.qcow2 \
     /var/lib/libvirt/images/openclaw-template.img
   ```

### Opcao B: A Partir da VM Multipass de Teste

Se ja existe uma VM Multipass configurada e testada:

```bash
# 1. Parar a VM
multipass stop openclaw-test

# 2. Localizar a imagem (macOS)
QCOW2_PATH=$(find /var/root/Library/Application\ Support/multipassd -name "*.qcow2" | head -1)

# 3. Compactar
qemu-img convert -c -O qcow2 "${QCOW2_PATH}" ~/Desktop/openclaw-template.img
```

> **Nota:** A imagem Multipass pode conter artefatos de teste. Preferir Opcao A para producao.

---

## 4. Importar no VirtFusion

### 4.1 Upload da Imagem

1. Acesse o painel **VirtFusion Admin**
2. Va em **Media** > **Operating System Images**
3. Clique em **Add Image**
4. Preencha:

| Campo | Valor |
|---|---|
| **Name** | `OpenClaw VPS` |
| **Version** | `1.0` |
| **OS Family** | `Linux` |
| **OS** | `Ubuntu` |
| **OS Version** | `24.04` |
| **Architecture** | `x86_64` |
| **Disk Driver** | `VirtIO` |
| **Network Driver** | `VirtIO` |

5. Faca upload do arquivo `.img` (QCOW2 compactado)

### 4.2 Configuracao do Template

1. Va em **Packages** ou **Plans**
2. Crie um plano (ou edite existente):

| Campo | Valor Sugerido |
|---|---|
| **Package Name** | `OpenClaw - Starter` |
| **vCPU** | 1-2 |
| **RAM** | 1-2 GB |
| **Disco** | 15-25 GB |
| **OS Image** | Selecionar `OpenClaw VPS` |
| **Bandwidth** | Conforme plano |

### 4.3 Cloud-Init

O template e compativel com cloud-init. O VirtFusion ira injetar automaticamente:

- **Hostname** da VPS
- **Chave SSH** do usuario (se configurada no painel)
- **Configuracao de rede** (IP, gateway, DNS)
- **Senha root** (se definida no painel)

Nao e necessario nenhum cloud-init userdata customizado.

---

## 5. O Que Acontece no Primeiro Boot

Sequencia automatica apos o usuario criar a VPS:

```
1. cloud-init         → Configura hostname, rede, SSH keys
2. firstboot.sh       → Gera token, cria .env, prepara diretorios
3. setup-web.service  → Inicia wizard Flask na porta 80
4. Usuario acessa     → http://IP_DA_VPS/
```

### Detalhes do Firstboot (`/opt/openclaw-setup/firstboot.sh`):

- Regenera SSH host keys (removidas no template)
- Regenera machine-id
- Cria diretorios `/root/.openclaw/` com permissoes corretas
- Gera token de acesso (64 chars hex) em `/var/lib/openclaw-token`
- Escreve `.env` inicial em `/opt/openclaw/.env`
- Marca sentinel `/var/lib/openclaw-firstboot-done`

### Detalhes do Wizard Web:

| Etapa | Acao |
|---|---|
| **1. Boas-vindas** | Exibe IP e instrucoes |
| **2. Token** | Usuario insere o token gerado (exibido no MOTD via SSH) |
| **3. API Keys** | Anthropic, OpenAI e/ou OpenRouter (pelo menos uma). Botao "Validar" testa a chave e carrega modelos disponiveis |
| **4. Telegram** | Token do bot (@BotFather) + pareamento automatico |
| **5. Deploy** | Executa onboard, configura gateway, inicia containers |

Apos o setup, o wizard se desativa automaticamente (`/var/lib/openclaw-setup-done`) e o Nginx passa a fazer proxy para o OpenClaw Gateway.

---

## 6. Portas e Firewall

| Porta | Servico | Quando |
|---|---|---|
| **22/tcp** | SSH | Sempre |
| **80/tcp** | Wizard (pre-setup) / Nginx proxy (pos-setup) | Sempre |
| **443/tcp** | HTTPS (futuro SSL) | Sempre aberta, Nginx nao escuta ate configurar SSL |
| **18789/tcp** | OpenClaw Gateway | Apos setup |
| **18790/tcp** | OpenClaw Bridge | Apos setup |

---

## 7. Estrutura de Arquivos na VPS

```
/opt/openclaw/                    # Repositorio OpenClaw + docker-compose.yml
  ├── .env                        # Variaveis de ambiente (API keys, tokens)
  └── docker-compose.yml          # Orquestracao dos containers

/opt/openclaw-setup/              # Wizard de setup
  ├── app.py                      # Aplicacao Flask
  ├── firstboot.sh                # Script de primeiro boot
  ├── requirements.txt            # Dependencias Python
  └── venv/                       # Virtualenv

/root/.openclaw/                  # Configuracao do OpenClaw (montada no container)
  ├── openclaw.json               # Config principal (gateway, modelo, channels)
  ├── agents/main/agent/          # Perfis de autenticacao
  │   └── auth-profiles.json
  └── workspace/                  # Workspace do agente

/etc/systemd/system/
  ├── openclaw-firstboot.service  # Executa uma vez no primeiro boot
  └── openclaw-setup-web.service  # Wizard web (ate o setup ser concluido)

/var/lib/
  ├── openclaw-firstboot-done     # Sentinel: firstboot ja executou
  ├── openclaw-setup-done         # Sentinel: setup concluido
  └── openclaw-token              # Token de acesso ao gateway
```

---

## 8. Containers Docker

Apos o setup, os seguintes containers estarao rodando:

| Container | Funcao | Porta |
|---|---|---|
| `openclaw-gateway` | API Gateway + Control UI | 18789 |
| `openclaw-bridge` | Bridge de canais (Telegram, etc.) | 18790 |
| `openclaw-sandbox` | Sandbox de execucao do agente | — |

Comandos uteis:

```bash
# Ver status dos containers
docker compose -f /opt/openclaw/docker-compose.yml ps

# Ver logs em tempo real
docker compose -f /opt/openclaw/docker-compose.yml logs -f

# Reiniciar todos os servicos
docker compose -f /opt/openclaw/docker-compose.yml restart

# Reiniciar apenas o gateway
docker compose -f /opt/openclaw/docker-compose.yml restart openclaw-gateway
```

---

## 9. Seguranca

| Item | Status |
|---|---|
| SSH host keys | Regeneradas no primeiro boot (unicas por VPS) |
| machine-id | Regenerado no primeiro boot (unico por VPS) |
| Token do gateway | Gerado aleatoriamente (64 chars hex) por VPS |
| Firewall UFW | Ativo, apenas portas necessarias |
| fail2ban | Ativo para SSH |
| Wizard | Auto-desativa apos setup concluido |
| API Keys | Salvas em `.env` (chmod 600) e `auth-profiles.json` |
| Docker logs | Limitados a 10MB x 3 arquivos (logrotate) |
| Swap | 1GB com swappiness=10 |

---

## 10. Troubleshooting

### Wizard nao aparece na porta 80

```bash
# Verificar se o firstboot rodou
cat /var/lib/openclaw-firstboot-done

# Verificar status do wizard
systemctl status openclaw-setup-web

# Ver logs
journalctl -u openclaw-setup-web -n 50 --no-pager

# Verificar se a porta esta ocupada
ss -tlnp | grep :80
```

### Token nao aparece no MOTD

```bash
# Verificar se o token foi gerado
cat /var/lib/openclaw-token

# Regenerar manualmente (se necessario)
openssl rand -hex 32 > /var/lib/openclaw-token
chmod 600 /var/lib/openclaw-token
```

### Containers nao iniciam apos setup

```bash
# Verificar .env
cat /opt/openclaw/.env

# Verificar openclaw.json
cat /root/.openclaw/openclaw.json | jq .

# Tentar subir manualmente
docker compose -f /opt/openclaw/docker-compose.yml up -d

# Ver logs de erro
docker compose -f /opt/openclaw/docker-compose.yml logs --tail=50
```

### Erro de permissao (EACCES) no onboard

```bash
# Recriar diretorios com permissoes corretas
mkdir -p /root/.openclaw/agents/main/agent /root/.openclaw/workspace
chown -R 1000:1000 /root/.openclaw
```

### Resetar VPS para novo setup (manter imagem)

```bash
docker compose -f /opt/openclaw/docker-compose.yml down
rm -rf /root/.openclaw
mkdir -p /root/.openclaw/agents/main/agent /root/.openclaw/workspace
chown -R 1000:1000 /root/.openclaw
rm -f /var/lib/openclaw-setup-done
systemctl restart openclaw-setup-web
```

---

## 11. Atualizacoes Futuras

Para atualizar o template:

1. Gerar nova imagem com as alteracoes
2. No VirtFusion, ir em **Media** > **Operating System Images**
3. Editar a imagem `OpenClaw VPS` e fazer upload da nova versao
4. VPS existentes **nao sao afetadas** — apenas novas criacoes usarao a imagem atualizada

Para atualizar VPS existentes (sem recriar):

```bash
cd /opt/openclaw
git pull origin main
docker build -t openclaw:local -f Dockerfile .
docker compose down
docker compose up -d
```

---

## 12. Checklist de Validacao

Antes de liberar para producao, verificar:

- [ ] Criar VPS a partir do template no VirtFusion
- [ ] cloud-init configura hostname e rede corretamente
- [ ] SSH funciona com a chave injetada pelo painel
- [ ] MOTD exibe token e IP corretos
- [ ] Wizard abre em `http://IP/`
- [ ] Token e aceito no Step 2
- [ ] Validacao de API key funciona (Anthropic, OpenAI, OpenRouter)
- [ ] Modelos sao carregados no dropdown apos validacao
- [ ] Bot Telegram pareia e responde
- [ ] Apos deploy, Gateway acessivel em `http://IP:18789/?token=TOKEN`
- [ ] Wizard nao aparece mais apos setup concluido
- [ ] `docker compose ps` mostra containers healthy
- [ ] UFW esta ativo com regras corretas
- [ ] fail2ban esta ativo
- [ ] Logs do Docker estao limitados (10MB x 3)
