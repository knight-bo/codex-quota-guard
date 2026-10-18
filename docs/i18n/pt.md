# Codex Quota Guard 0.5.0: instalação e utilização

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
- «Monitoriza a quota desta tarefa a cada 30 segundos. Avisa-me quando restarem 82 % e, aos 81 %, pergunta-me se quero pausá-la quando restarem 80 %.»
- «Para a monitorização da quota.»

Uma consulta pontual não inicia verificações periódicas. Antes de iniciar uma monitorização contínua, o assistente anfitrião tem de identificar a tarefa concreta, conseguir executar a CLI numa sessão supervisionada em segundo plano, processar os seus eventos e manter a conversa disponível para as suas respostas. Se não conseguir cumprir estas condições, deve explicar a limitação e oferecer apenas uma consulta pontual, sem afirmar que a monitorização contínua está ativa.

A partir da raiz do pacote:

```sh
# Consulta manual em português:
python3 scripts/quota_guard.py read --bucket codex --state-dir STATE --format text --locale pt
python3 scripts/quota_guard.py read --bucket codex --target 80 --task-key TASK --warn-margin 2 --confirm-margin 1 --state-dir STATE --format text --locale pt
# O anfitrião tem de supervisionar esta sessão em segundo plano e processar o JSON produzido por predefinição:
python3 scripts/quota_guard.py start --bucket codex --target 80 --task-key TASK --warn-margin 2 --confirm-margin 1 --interval 30 --state-dir STATE
# Noutra sessão, com o mesmo diretório de estado:
python3 scripts/quota_guard.py stop --state-dir STATE --format text --locale pt
```

Substitua `TASK` pela identidade estável e verificada da tarefa concreta a monitorizar; não invente uma identidade nem inclua segredos. A associação guardada e emitida utiliza um hash, nunca o identificador original, e não concede autorização para controlar a tarefa. Substitua `STATE` pelo caminho absoluto de um diretório privado (0700), pertencente ao seu utilizador, fora do repositório e da cache do plugin, sob um diretório superior de confiança com permissão de escrita. Não utilize `chmod` para contornar restrições de acesso. Use exatamente o mesmo diretório para parar a monitorização. `codex` é um exemplo de grupo de quota; selecione explicitamente o grupo adequado ao trabalho e utilize diretórios de estado separados para grupos diferentes.

`start` continua a ser um processo em primeiro plano, não um serviço autónomo: o anfitrião tem de conservar e supervisionar a respetiva sessão em segundo plano. Após solicitar a paragem, verifique se o processo terminou; o pedido, por si só, não o comprova. Parar a monitorização não para a tarefa observada.

## Objetivo de quota restante e confirmação

`--target` aceita qualquer percentagem finita de quota **restante** entre 0 e 100, inclusive, incluindo decimais como `37.5`. Não representa a percentagem consumida. As margens predefinidas são de 2 pontos percentuais para o aviso e de 1 ponto para a confirmação. Com um objetivo de 80:
- Quando restam 82 % ou menos, é emitido `warning`.
- Quando restam 81 % ou menos, é emitido `confirmation_required`; o anfitrião deve identificar a tarefa e perguntar: «Queres que pause esta tarefa quando restarem 80 %?»
- Quando restam 80 % ou menos, é emitido `target_reached` e é recusada a admissão de novo trabalho (`allow_new_work=false`). Esta decisão cooperativa de admissão não pausa efetivamente a tarefa.

As margens são expressas em pontos percentuais e aceitam valores finitos de 0 a 100; a margem de aviso tem de ser maior ou igual à de confirmação. Cada limiar de ativação fica limitado a 100 %. As margens não alteram o limiar de admissão: este continua a ser exatamente o objetivo, com um buffer efetivo de 0.

Se a primeira leitura válida já estiver no objetivo ou abaixo dele, deve perguntar-se de imediato: «Já restam 80 % ou menos. Queres pausar esta tarefa agora?» Com um objetivo de 100, a pergunta é imediata mesmo que ainda restem 100 %. Um objetivo de 0 não garante que a quota não se esgote. Se várias etapas coincidirem numa leitura, devem ser agrupadas numa só mensagem, sem repetir a pergunta.

Um evento não prova que o utilizador tenha sido notificado, que tenha autorizado uma ação ou que a tarefa esteja pausada. O anfitrião tem de fazer a pergunta e verificar a resposta real. O silêncio não é consentimento. Qualquer ação exige autorização explícita para a tarefa concreta e uma via de controlo suportada e verificada; se esta não existir, deve explicar-se o impedimento e pedir ao utilizador que intervenha manualmente. Não se podem pausar nem terminar tarefas arbitrárias. Antes de afirmar que uma tarefa foi pausada ou parada, é necessário verificar o seu estado real.

Depois de atingido o objetivo, o bloqueio de admissão mantém-se mesmo que a quota aumente ou seja reposta, ou que a monitorização da mesma tarefa e objetivo seja reiniciada. O trabalho nunca é retomado automaticamente. Para alterar a configuração, acorde os novos valores, pare a monitorização e verifique o fim do processo antes de a voltar a iniciar. Utilize `--new-cycle` apenas quando o utilizador pedir expressamente um novo ciclo de monitorização, depois de parar o anterior; isto não autoriza uma pausa nem uma retoma. Os eventos são registados, no máximo, uma vez: se um se perder, consulte o estado e o histórico real da conversa; a ausência de um novo evento não prova que já tenha sido pedida ou obtida autorização.

## Compatibilidade com o modo de reserva

O modo antigo `--reserve 10 --buffer 2` mantém-se apenas como opção de compatibilidade. Nesse modo, a deteção ocorre quando restam 12 % ou menos e não garante a conservação de 10 %. Não combine `--target` com `--reserve`, `--threshold` ou `--buffer`; a CLI rejeita essas combinações. Uma reserva antiga de 10 % nunca substitui o objetivo escolhido, mesmo que este seja inferior a 10 %.

## Limites

As verificações periódicas podem detetar a passagem pelo limiar com atraso ou saltar a percentagem exata; o atraso dos dados e o consumo de outros clientes impedem garantir uma paragem exatamente no objetivo. Dados em falta, inválidos, sintéticos ou desatualizados não representam um saldo atual nem provam que um limiar tenha sido atingido ou ultrapassado. O plugin não controla tarefas arbitrárias na nuvem. O seu campo `checkpoint_status` permanece sempre `unconfirmed`; apenas o orquestrador responsável verifica de forma independente a gravação e a conclusão. Uma interrupção gerida exige autorização explícita para a conversa e o turno exatos e acessíveis. A confirmação de uma interrupção não confirma a conclusão da tarefa, a gravação de um ponto de recuperação nem a possibilidade de retomar o trabalho. Este mecanismo antigo não permite contornar a confirmação do modo de objetivo; `--target` rejeita `--allow-interrupt`.

Mais informações: [Contrato de confirmação do anfitrião (em inglês)](../CONFIRMATION-WORKFLOW.md) · [README](../../README.md) · [Idiomas](../LANGUAGES.md).


## Anúncios públicos opcionais de Tibo

Diga «Vigia os anúncios públicos de reposição do Tibo a cada hora», «Avisa apenas de completed e banked em Asia/Shanghai», «Consulta os anúncios uma vez» ou «Para os avisos públicos». É usado o comando separado `resetwatch`. Uma pergunta significa um único `read`; iniciar exige um pedido explícito de monitorização. O anfitrião deve supervisionar o processo em primeiro plano, ler JSON e usar o adaptador local de notificações existente. Sem esse canal, deve explicar que só há saída de texto/JSON. A instalação não inicia nada.

`planned` é um plano, não uma conclusão; `completed` é um relato de terceiros sobre um anúncio de conclusão; `banked` é uma reposição guardada sem confirmação de receção ou utilização manual; `manual_credit` anuncia crédito manual cujas condições originais devem ser verificadas. Um anúncio não confirma a quota pessoal, não resgata crédito nem retoma/pausa a investigação automaticamente. Mesmo «verificado diretamente» é uma afirmação do fornecedor, não confirmação independente nem API oficial.

Substitua PUBLIC_STATE por um diretório pai absoluto privado fora do repositório/cache. `PUBLIC_STATE/public-reset-watch`, bloqueio e token de paragem são independentes e não alteram o estado da quota. A primeira obtenção bem-sucedida cria uma referência silenciosa. Publicações históricas, duplicados, reinícios e estados antigos fora de ordem não repetem alertas. Uma atualização planned→completed só pode emitir o novo estado. Alterar filtros não repete o histórico. Para mudar definições, pare, confirme o fim do processo e reinicie; não para a investigação nem o monitor de quota.

`--events` seleciona planned,completed,banked,manual_credit (todos por predefinição). `--interval`: 3600..86400 segundos, predefinição 3600. A espera persiste após reinícios; o recuo depois de erros limita-se a 24 horas. `--max-age` limita a idade das provas de obtenção/verificação em cache (172800 segundos, pelo menos o intervalo e no máximo 604800); `--event-age`, a de novas publicações (604800, intervalo 3600..2592000). `--timeout` global: 1..30 segundos (10), com no máximo mais um tempo limite de socket. `--timezone` usa um fuso IANA instalado, UTC por predefinição; as datas máquina ficam UTC. `--locale` mantém as regras de substituição; campos e valores JSON não são traduzidos.

Por predefinição, `--provider modelyard` lê apenas o RSS público fixo `/feed.xml`. HTML e o `--provider-url` arbitrário foram removidos; trocar fonte exige revisão de código. As categorias RSS são relatos de terceiros, não verificação oficial. `fetched_at` é prova local de obtenção; lastBuildDate/última publicação não prova sincronização. Um feed antigo válido pode criar a referência, com cobertura desconhecida. O âmbito segue o texto original fornecido ou fica desconhecido; título/contexto são afirmações do fornecedor. Registos apenas de ChatGPT não são enviados como Codex/Work. Uma mudança de categoria do mesmo post usa `first_observed_status_at` como atualização local do agregador, sem inventar data de edição. O callback usa uma via local existente do anfitrião; entrega real não verificada. Rede/descarga Library bloqueadas aqui; testa-se o primeiro item real recortado fornecido diretamente. Robots não autoriza redistribuição; veja as fontes.

Falha de rede/HTTP, verificação expirada, formato/datas inválidos e fonte forjada significam desconhecido, nunca «reposto» ou «não reposto»; não criam eventos. Uma consulta bem-sucedida sem novos eventos não prova ausência de reposição. `status` é cache, não nova consulta nem prova de execução. O registo é guardado antes da saída: uma falha pode perder a entrega e um evento não prova notificação. Suspensão, saída e atrasos de rede/fonte interrompem a cobertura. Sem garantia de tempo real nem arranque automático; não exige nova conta, API paga, envio de dados pessoais nem nova permissão de notificação do sistema.

```sh
python3 scripts/quota_guard.py resetwatch --help --locale pt
python3 scripts/quota_guard.py resetwatch read --state-dir PUBLIC_STATE --format text --locale pt
python3 scripts/quota_guard.py resetwatch start --state-dir PUBLIC_STATE --events completed,banked --interval 3600 --timezone Asia/Shanghai
python3 scripts/quota_guard.py resetwatch stop --state-dir PUBLIC_STATE --format text --locale pt
python3 scripts/quota_guard.py resetwatch status --state-dir PUBLIC_STATE --format text --locale pt
```

A monitorização pública exige apenas Python/POSIX/rede e dados IANA instalados; não exige a CLI oficial Codex nem uma conta.

`--fixture FILE` serve apenas para `read`, sem rede/conta e com estado sintético isolado; uma data antiga pode ser corretamente marcada como expirada.

[Contrato / JSON](../RESET-WATCH.md) · [Revisão de fontes](../RESET-SOURCES.md)
