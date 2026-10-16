# Codex Quota Guard: instalação e utilização

Requisitos: Python 3.10 ou posterior, um sistema POSIX e a CLI oficial do Codex, autenticada com uma conta elegível para consultar a quota. Utilize o procedimento normal de autorização e início de sessão. Não contorne permissões nem autenticação, não altere `CODEX_HOME` para evitar restrições e não leia diretamente credenciais ou ficheiros de sessão.

## Instalação

Execute:

```sh
codex plugin marketplace add knight-bo/codex-quota-guard
```

Reinicie a aplicação de computador, selecione **Codex Quota Guard Local**, instale o plugin e ative-o. A publicação no GitHub não representa aprovação no diretório público de plugins. A instalação não inicia a monitorização nem configura um arranque automático.

## Consultar, iniciar e parar

Exemplos de pedidos:
- «Consulta a quota restante do Codex.»
- «Inicia a monitorização com uma reserva de 10 %, uma margem de 2 pontos percentuais e verificações a cada 30 segundos.»
- «Para a monitorização da quota.»

Uma consulta pontual não inicia verificações periódicas. A partir da raiz do pacote:

```sh
python3 scripts/quota_guard.py read --bucket codex --state-dir STATE --format text --locale pt
python3 scripts/quota_guard.py start --bucket codex --reserve 10 --buffer 2 --interval 30 --state-dir STATE --format text --locale pt
# Noutro terminal, enquanto start continua em primeiro plano:
python3 scripts/quota_guard.py stop --state-dir STATE --format text --locale pt
```

Substitua `STATE` pelo caminho absoluto de um diretório privado (0700), pertencente ao seu utilizador, fora do repositório e da cache do plugin, sob um diretório superior de confiança com permissão de escrita. Não utilize `chmod` para contornar restrições de acesso. Use exatamente o mesmo diretório para parar a monitorização. `codex` é um exemplo de grupo de quota; selecione explicitamente o grupo adequado ao trabalho.

`start` funciona em primeiro plano: mantenha a sessão supervisionada. Após solicitar a paragem, verifique se o processo terminou; o pedido, por si só, não o comprova.

## Limites

A deteção ocorre quando restam 12 % ou menos: reserva de 10 % mais 2 pontos de margem. Não garante a conservação de 10 %. Outros clientes podem consumir quota. Dados inválidos ou desatualizados não representam um saldo atual. O plugin não controla tarefas arbitrárias na nuvem. O seu campo `checkpoint_status` permanece sempre `unconfirmed`; apenas o orquestrador responsável verifica de forma independente a gravação e a conclusão. Uma interrupção gerida exige autorização explícita para a conversa e o turno exatos e acessíveis. A confirmação de uma interrupção não confirma a conclusão da tarefa.

Mais informações: [README](../../README.md) · [Idiomas](../LANGUAGES.md).
