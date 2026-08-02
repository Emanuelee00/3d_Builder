# Fase 6 — Aprire le porte nella Security List Oracle (non scriptabile via SSH)

`ufw` (fase 1) apre le porte solo *dentro* la VM. Oracle Cloud ha **anche** un firewall
a livello di rete cloud (Security List della VCN) che va configurato dalla console web —
di default lascia passare solo la porta 22 (SSH). Senza questo passaggio il sito non è
raggiungibile da internet anche se il server gira correttamente.

## Passi nella console Oracle Cloud

1. Menu ☰ → **Networking** → **Virtual Cloud Networks**
2. Apri la VCN creata insieme alla VM (es. `vcn-20260709-0130`)
3. Nel menu laterale, click **Security Lists**
4. Click sulla security list di default (di solito `Default Security List for vcn-...`)
5. Click **Add Ingress Rules**
6. Aggiungi una regola per ciascuna porta che serve:

| Source CIDR | IP Protocol | Destination Port Range | Note |
|---|---|---|---|
| `0.0.0.0/0` | TCP | `3000` | Next.js in sviluppo/test diretto |
| `0.0.0.0/0` | TCP | `80` | HTTP (quando c'è un reverse proxy nginx) |
| `0.0.0.0/0` | TCP | `443` | HTTPS (quando c'è un certificato) |

7. Click **Add Ingress Rules** per salvare

`0.0.0.0/0` = raggiungibile da qualsiasi indirizzo su internet (necessario per un sito
pubblico). Nessun riavvio della VM richiesto, le regole si applicano subito.

## Verifica

Dal tuo PC (fuori dalla rete della VM):

```powershell
Test-NetConnection -ComputerName <IP_PUBBLICO_VM> -Port 3000
```

`TcpTestSucceeded : True` conferma che la porta è raggiungibile dall'esterno.
