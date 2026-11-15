# Guia do utilizador

<span class="no-pdf">
    [ :material-file-pdf-box: Descarregar versão PDF](assets/documents/seis-lab-data-user-guide.pdf){ .md-button .no-pdf }
</span>

O SeisLabData é uma aplicação web para a catalogação de dados de levantamentos marinhos. Mantém
um catálogo de projetos, das missões realizadas no âmbito de cada projeto e dos registos que
descrevem os ficheiros de dados produzidos por cada missão. Os ficheiros de dados permanecem no
sistema de ficheiros do arquivo; o catálogo guarda os seus metadados, a sua localização no arquivo
e pré-visualizações derivadas.

Os registos podem ser criados manualmente ou gerados por uma descoberta da missão, que percorre o
diretório da missão no arquivo e cria um registo para cada ficheiro que corresponde aos padrões
de caminho configurados, extraindo do próprio ficheiro a sua extensão espacial, a sua extensão
temporal e outros metadados.

O catálogo é publicado através da interface web e de uma API STAC, disponível no caminho `/stac`,
que expõe apenas os itens públicos.

A interface está disponível em português e em inglês. O idioma é selecionado no menu de idioma
da barra superior. Os dados introduzidos pelos utilizadores, como nomes e descrições, não são
traduzidos.

!!! note "Etiquetas da interface"

    Algumas etiquetas da interface ainda não têm tradução para português e são apresentadas em
    inglês. Este guia reproduz as etiquetas tal como são apresentadas na interface em português.


## Conceitos

### Projetos, missões, registos e recursos

O catálogo está organizado numa hierarquia:

```
Projeto
  └── Missão (várias por projeto)
        └── Registo (vários por missão)
              └── Recurso (vários por registo)
```

- **Projeto** - O agrupamento de nível superior, correspondendo normalmente a um contrato ou a um
  estudo. Um projeto contém missões.
- **Missão** - Uma campanha de recolha de dados no âmbito de um projeto. Uma missão está
  associada a um diretório do arquivo, o seu caminho relativo, e contém registos.
- **Registo** - A descrição de um conjunto de dados produzido por uma missão, por exemplo uma
  grelha batimétrica processada ou uma linha sísmica. Um registo é classificado por uma categoria
  e por um estádio e contém um ou mais recursos.
- **Recurso** - Um ficheiro pertencente a um registo. Os recursos de dados referem-se a ficheiros
  do arquivo. Os recursos derivados, como as pré-visualizações, são gerados pela aplicação.

Os projetos, as missões e os registos partilham um conjunto de propriedades comuns:

| Propriedade | Descrição |
|-------------|-----------|
| Nome | Identifica o item. Até 100 caracteres. |
| Descrição | Descrição breve do item. Até 500 caracteres. |
| Extensão espacial | Retângulo envolvente do item, em longitude e latitude WGS 84. |
| Extensão temporal | Datas de início e de fim do item. |
| Ligações | Até 5 ligações para recursos externos, cada uma com um URL, um tipo de media, uma relação e uma descrição. |
| Estado | Estado atual do item, descrito em [Estado dos itens](#estado-dos-itens). |

Os registos podem ainda ser relacionados com outros registos, como descrito em
[Relacionar registos entre si](#relacionar-registos-entre-si).

### Estado dos itens

Cada projeto, missão e registo tem um estado. Os estados estáveis são aqueles em que um item pode
ser modificado pelos utilizadores. Os estados transitórios são mantidos enquanto uma tarefa em
segundo plano trabalha sobre o item.

**Estados estáveis:**

- **rascunho** - O item é visível apenas para utilizadores autenticados.
- **público** - O item é visível para todos os utilizadores, incluindo os anónimos.

Os itens não são publicados nem despublicados manualmente. Após cada criação ou atualização, o
item é validado e o seu estado é definido da seguinte forma:

- Um projeto é publicado se for válido, e passa a rascunho caso contrário.
- Uma missão é publicada se for válida e o seu projeto estiver público.
- Um registo é publicado se for válido e a sua missão estiver pública.

As alterações propagam-se aos itens inferiores:

- Quando um projeto válido é atualizado, as suas missões válidas em rascunho são publicadas,
  seguidas dos respetivos registos válidos em rascunho.
- Quando um projeto deixa de ser válido, as suas missões e os respetivos registos passam a
  rascunho.
- Quando uma missão é atualizada, os seus registos válidos em rascunho são publicados se a missão
  estiver pública, e passam a rascunho caso contrário.

Um item é válido quando:

- o seu nome tem entre 5 e 100 caracteres;
- a sua descrição tem até 500 caracteres;
- todas as ligações têm um URL `http` ou `https`;
- tem uma extensão espacial com área não nula;
- no caso dos registos, a categoria e o estádio estão definidos.

A extensão temporal é opcional. Para os itens em rascunho, o painel de informação da página de
detalhe indica se o item é válido e lista os erros de validação.

**Estados transitórios:**

| Estado | Aplica-se a | Mantido enquanto |
|--------|-------------|------------------|
| em validação | projetos, missões, registos | o item é validado após uma criação ou atualização |
| em descoberta | missões | decorre uma descoberta da missão |
| a cancelar descoberta | missões | foi pedido o cancelamento de uma descoberta em curso e este está a ser processado |
| em derivação | registos | as pré-visualizações geradas estão a ser guardadas |
| em exportação | registos | o registo está a ser exportado para o GeoNode |

Enquanto um item se encontra num estado transitório, não pode ser atualizado nem eliminado. Além
disso:

- Enquanto uma missão está em descoberta ou a cancelar descoberta, os seus registos não podem ser
  criados, atualizados nem eliminados, as atualizações em massa ignoram-nos e não pode ser
  iniciada outra descoberta da missão.
- Um projeto não pode ser eliminado enquanto alguma das suas missões ou registos estiver num
  estado transitório. Uma missão não pode ser eliminada enquanto algum dos seus registos estiver
  num estado transitório.

No fim de uma tarefa, o item regressa ao estado que tinha antes do início da tarefa.

### Descoberta de missões

Uma descoberta da missão percorre o diretório da missão no arquivo e cria um registo para cada
ficheiro que corresponde a uma configuração de descoberta de recursos. Cada registo contém um
recurso de dados que aponta para o seu ficheiro. A extensão espacial e a extensão temporal do
registo são extraídas dos metadados do ficheiro, e a sua categoria e o seu estádio são obtidos da
configuração.

A descoberta é configurada através das configurações de descoberta de recursos, descritas em
[Configurações de descoberta de recursos](#configuracoes-de-descoberta-de-recursos). É iniciada
na página de detalhe da missão, como descrito em
[Descobrir o conteúdo de uma missão](#descobrir-o-conteudo-de-uma-missao).


## Utilizadores e permissões

Os **utilizadores anónimos** podem consultar e pesquisar os projetos, missões e registos
públicos, descarregar os recursos dos registos públicos e usar a API STAC. Os itens não públicos
não lhes são apresentados.

Os **utilizadores autenticados** podem ver todos os itens, incluindo os rascunhos. O que podem
modificar depende das suas funções:

| Função | Permissões |
|--------|------------|
| nenhuma | Acesso de leitura a todos os itens, incluindo os rascunhos. |
| `catalog-editor` | Acesso total: criar, atualizar e eliminar projetos, missões, registos e definições, executar e cancelar descobertas, atualizar registos em massa e exportar registos para o GeoNode. |
| `system-admin` | As mesmas permissões de `catalog-editor`, e ainda o acesso à interface de administração do Authentik através do menu do utilizador. |

As permissões não dependem de quem criou um item: os utilizadores com a função `catalog-editor`
ou `system-admin` podem modificar qualquer item.

As contas de utilizador e as funções são geridas no [Authentik](https://goauthentik.io/), o
serviço de autenticação usado pela plataforma. Os utilizadores iniciam sessão através da ligação
**Entrar** da barra superior, que conduz à página de início de sessão do Authentik. A plataforma
não permite o registo autónomo: as contas são criadas por um administrador do sistema no
Authentik.

O menu do utilizador da barra superior apresenta o nome de utilizador, o e-mail, o identificador
e as funções do utilizador autenticado.


## Trabalhar com projetos

Um projeto agrupa as missões de um contrato ou estudo. As suas propriedades são as propriedades
comuns listadas em [Projetos, missões, registos e recursos](#projetos-missoes-registos-e-recursos).

A página de detalhe do projeto apresenta as suas propriedades, um mapa com a sua extensão
espacial, um resumo dos seus registos por categoria e por estádio, e a lista das suas missões. A
seleção de uma categoria ou de um estádio no resumo abre a lista dos registos do projeto com essa
categoria ou esse estádio.

### Pesquisar projetos

A listagem de projetos está disponível em `/projects/`. Os resultados são ordenados pelo fim da
sua extensão temporal, do mais recente para o mais antigo, depois pelo início da sua extensão
temporal e pelo nome, e são apresentados em páginas de 20 itens.

Estão disponíveis os seguintes filtros:

| Filtro | Descrição |
|--------|-----------|
| search projects | Projetos cujo nome contém o texto indicado, sem distinção entre maiúsculas e minúsculas. |
| show only internal projects | Apenas os projetos que não estão públicos. Disponível para utilizadores autenticados. |
| Data de início, Data de fim | Projetos cuja extensão temporal está compreendida entre as datas indicadas. Os projetos sem extensão temporal também são incluídos. |
| Mapa | Projetos cuja extensão espacial interseta a área visível do mapa. Os projetos sem extensão espacial também são incluídos. Os resultados são atualizados quando o mapa é deslocado. |

Os filtros temporais e o filtro do mapa são apresentados com o botão
**toggle advanced search controls**. A seleção da extensão de um projeto no mapa abre a página de
detalhe do projeto.

### Criar um projeto

Os utilizadores com a função `catalog-editor` ou `system-admin` podem criar um projeto com o botão
**Add new project** da listagem de projetos. O formulário tem os seguintes campos:

| Campo | Descrição |
|-------|-----------|
| Nome | Obrigatório. Identifica o projeto e deve ser único entre todos os projetos. Até 100 caracteres; um projeto válido requer pelo menos 5. |
| Descrição | Opcional. Resumo do projeto, até 500 caracteres. |
| Extensão espacial | Longitude e latitude mínimas e máximas da área abrangida pelo projeto, em graus decimais, introduzidas como números ou desenhadas como um retângulo no mapa. Um projeto válido requer uma extensão com área não nula. |
| Data de início, Data de fim | Opcional. Datas de início e de fim do projeto. |
| Ligações | Opcional. Até 5 ligações para recursos externos relacionados com o projeto, adicionadas com **Adicionar outra ligação**. Cada ligação tem um URL, que deve usar `http` ou `https`, um tipo de media, uma relação e uma descrição de até 500 caracteres. |

O projeto é criado com o botão **Criar projeto**. É depois validado e, se for válido, publicado.
Após cada criação e atualização é gerada uma miniatura que apresenta a sua extensão espacial sobre
um mapa de base.

### Atualizar um projeto

O botão **editar projeto** da página de detalhe do projeto abre um formulário com os mesmos campos
do formulário de criação. A gravação do formulário valida novamente o projeto e atualiza o estado
do projeto, das suas missões e dos seus registos, como descrito em
[Estado dos itens](#estado-dos-itens).

### Eliminar um projeto

O botão **delete project** da página de detalhe do projeto elimina o projeto após uma
confirmação. A eliminação de um projeto elimina também as suas missões, os respetivos registos e
os recursos dos registos. Os ficheiros do arquivo não são modificados.


## Trabalhar com missões

Uma missão é uma campanha de recolha de dados no âmbito de um projeto. Além das propriedades
comuns listadas em [Projetos, missões, registos e recursos](#projetos-missoes-registos-e-recursos),
uma missão tem as seguintes propriedades:

| Propriedade | Descrição |
|-------------|-----------|
| Caminho relativo | Caminho do diretório da missão no arquivo, relativo à raiz do arquivo. A descoberta percorre este diretório, e os caminhos dos recursos da missão são relativos a ele. |
| CRS implícito | Código EPSG do sistema de referência de coordenadas assumido para os ficheiros descobertos que não declaram um. |

A página de detalhe da missão apresenta as suas propriedades, um mapa com a sua extensão
espacial, um resumo dos seus registos por categoria e por estádio, e a lista dos seus registos.

### Pesquisar missões

As missões são listadas em dois locais:

- A listagem de missões, em `/survey-missions/`, lista as missões de todos os projetos. Oferece
  os filtros **search survey missions** e **show only internal survey missions** e os filtros
  temporais e do mapa, como descrito em [Pesquisar projetos](#pesquisar-projetos).
- A página de detalhe do projeto lista as missões do projeto, com uma pesquisa por nome e o
  filtro **show only internal items**.

A página inicial apresenta as três missões mais recentes.

### Criar uma missão

Uma missão é criada com o botão **add new survey mission** da página de detalhe do seu projeto. O
formulário tem os seguintes campos:

| Campo | Descrição |
|-------|-----------|
| Nome | Obrigatório. Identifica a missão e deve ser único entre as missões do projeto. Até 100 caracteres; uma missão válida requer pelo menos 5. |
| Descrição | Opcional. Resumo da missão, até 500 caracteres. |
| Caminho relativo | Opcional. Caminho do diretório da missão no arquivo, relativo ao diretório raiz do arquivo. Necessário para executar uma descoberta. |
| CRS implícito | Obrigatório. Código EPSG assumido para os ficheiros descobertos que não declaram um sistema de referência de coordenadas. O valor por omissão é 32629 (WGS 84 / UTM zona 29N). A introdução de um código ou do nome de um CRS apresenta sugestões correspondentes. O código deve identificar um CRS projetado ou geográfico. |
| Extensão espacial | Longitude e latitude mínimas e máximas da área abrangida pela missão, em graus decimais, introduzidas como números ou desenhadas como um retângulo no mapa. Uma missão válida requer uma extensão com área não nula. |
| Data de início, Data de fim | Opcional. Datas de início e de fim da campanha de recolha de dados. |
| Ligações | Opcional. Até 5 ligações para recursos externos relacionados com a missão. Cada ligação tem um URL, que deve usar `http` ou `https`, um tipo de media, uma relação e uma descrição de até 500 caracteres. |

O CRS implícito é usado para os ficheiros cujo formato não permite declarar um sistema de
referência de coordenadas, como os ficheiros XYZ e alguns ficheiros SEG-Y. As missões fora da zona
UTM 29N, por exemplo em torno da Madeira ou dos Açores, requerem a definição do CRS
correspondente. Com um CRS implícito geográfico, as coordenadas expressas em metros ficam fora dos
intervalos válidos de longitude e latitude, e os registos desses ficheiros são criados sem
extensão espacial.

### Atualizar uma missão

O botão **editar missão** da página de detalhe da missão abre um formulário com os mesmos campos
do formulário de criação. O botão está desativado enquanto a missão se encontra num estado
transitório.

### Descobrir o conteúdo de uma missão

O botão **descobrir registos...** da página de detalhe da missão inicia uma descoberta após uma
confirmação. O botão está desativado quando a missão não tem caminho relativo ou se encontra num
estado transitório. A descoberta requer:

- a função `catalog-editor` ou `system-admin`;
- uma missão no estado rascunho ou público;
- um caminho relativo que designe um diretório dentro do arquivo, diferente da raiz do arquivo.

Enquanto a descoberta decorre:

- a missão está em descoberta, e os seus registos não podem ser criados, atualizados nem
  eliminados;
- o painel de ações apresenta o seu progresso, como o número de ficheiros encontrados, o número de
  registos criados e, quando aplicável, o número de ficheiros que não foi possível processar e os
  nomes das configurações de descoberta de recursos com um padrão de caminho inválido;
- a lista de registos da missão é atualizada a cada atualização do progresso.

É apresentada uma notificação quando a descoberta se inicia e quando termina, é cancelada ou
falha.

A descoberta cria um registo para cada ficheiro que corresponde a uma configuração de descoberta
de recursos e que ainda não é referido por um registo da missão. O registo recebe o nome do
ficheiro, obtém a sua categoria e o seu estádio da configuração correspondente e contém um recurso
de dados que se refere ao ficheiro. A sua extensão espacial e a sua extensão temporal são
extraídas dos metadados do ficheiro. Os outros metadados extraídos são apresentados na página de
detalhe do registo. Para os ficheiros cujos metadados não identificam um sistema de referência de
coordenadas, é usado o CRS implícito da missão.

Os registos criados pela descoberta são validados à medida que são criados. No fim da descoberta,
os registos válidos são publicados se a missão estiver pública, e os restantes registos
permanecem em rascunho. Isto aplica-se também quando a descoberta é cancelada, falha ou excede o
seu tempo limite, aos registos criados até esse momento.

Para alguns formatos, os metadados são extraídos de amostras do ficheiro e não do ficheiro
completo:

- Os ficheiros KMALL são lidos em 16 janelas de 256 KB, nas duas pontas do ficheiro e igualmente
  espaçadas entre elas.
- Os ficheiros XYZ cujos pontos não formam uma grelha regular, como as sondagens aceites, são
  lidos em 128 janelas de 64 KB, e o seu número de pontos é estimado.

As extensões resultantes são aproximações. Ver [Formatos suportados](https://seis-lab-data.ipma.pt/docs/pt/supported-formats/) para os
formatos a partir dos quais são extraídos metadados.

São geradas pré-visualizações para os registos criados cuja configuração tem a opção
**Gerar pré-visualizações** ativa, enquanto a descoberta decorre. No fim da descoberta, são também
pedidas pré-visualizações para os registos mais antigos da missão que não as têm.

**Executar novamente uma descoberta** ignora os ficheiros que já são referidos por um registo da
missão. Se um desses registos não tiver extensão espacial e o CRS implícito da missão for
projetado, a sua extensão espacial, a sua extensão temporal e os outros metadados do ficheiro são
extraídos novamente. Isto permite corrigir os registos de uma missão que foi descoberta com um CRS
implícito inadequado: corrigir o CRS implícito e executar novamente a descoberta.

**Cancelar uma descoberta:** o botão **cancelar descoberta...** interrompe uma descoberta em curso
após uma confirmação. A missão passa ao estado a cancelar descoberta até a descoberta parar. Os
registos criados até esse momento são mantidos. Se o processo de descoberta já não estiver em
execução, por exemplo após um reinício do servidor, um novo pedido de cancelamento restaura a
missão após 10 minutos sem progresso.

Se não tiver terminado antes, uma descoberta para ao fim de 24 horas. Os registos criados até esse
momento são mantidos, e uma nova execução da descoberta continua com os ficheiros restantes.

### Eliminar uma missão

O botão **delete survey mission** da página de detalhe da missão elimina a missão após uma
confirmação. A eliminação de uma missão elimina também os seus registos e os respetivos recursos.
Os ficheiros do arquivo não são modificados. O botão está desativado enquanto a missão se encontra
num estado transitório.


## Trabalhar com registos

Um registo descreve um conjunto de dados produzido por uma missão. Além das propriedades comuns
listadas em [Projetos, missões, registos e recursos](#projetos-missoes-registos-e-recursos), um
registo tem as seguintes propriedades:

| Propriedade | Descrição |
|-------------|-----------|
| Categoria | Classificação do conjunto de dados, como descrito em [Categorias](#categorias). |
| Estádio | Estádio de processamento do conjunto de dados, como descrito em [Estádios](#estadios). |
| Recursos | Ficheiros pertencentes ao registo, como descrito em [Trabalhar com recursos dos registos](#trabalhar-com-recursos-dos-registos). |
| Registos relacionados | Relações com outros registos, como descrito em [Relacionar registos entre si](#relacionar-registos-entre-si). |

A página de detalhe do registo apresenta as suas propriedades, um mapa com a sua extensão
espacial e, quando disponível, a sua pré-visualização, as suas relações com outros registos e os
seus recursos de dados, com um botão de descarga para cada um. A página apresenta também os
metadados extraídos do ficheiro de dados do registo, como o formato, o CRS e o tamanho do
ficheiro.

### Pesquisar registos

Os registos são listados em dois locais:

- A listagem de registos, em `/survey-related-records/`, lista os registos de todas as missões.
- A página de detalhe da missão lista os registos da missão.

Ambas as listagens oferecem os seguintes filtros:

| Filtro | Descrição |
|--------|-----------|
| search survey-related records | Registos cujo nome contém o texto indicado, sem distinção entre maiúsculas e minúsculas. |
| show only internal survey-related records | Apenas os registos que não estão públicos. Disponível para utilizadores autenticados. |
| categoria | Registos com a categoria selecionada. |
| estádio | Registos com o estádio selecionado. |
| media type | Registos com um recurso do tipo de media indicado. |
| Data de início, Data de fim | Como descrito em [Pesquisar projetos](#pesquisar-projetos). |
| Path | Registos com um recurso cujo caminho relativo contém o texto indicado. |

A listagem de registos oferece ainda os filtros **projeto** e **mission**, e o filtro do mapa
descrito em [Pesquisar projetos](#pesquisar-projetos).

As listas de registos oferecem as seguintes ações:

- **select all on this page** e **Select all records that match your search** selecionam
  registos para uma atualização em massa; **clear selection** limpa a seleção.
- **bulk update** abre o formulário de atualização em massa para os registos selecionados. Está
  disponível na página de detalhe da missão, para os utilizadores com a função `catalog-editor`
  ou `system-admin`, enquanto a missão não está em descoberta.
- **ligações para descarregar** produz um ficheiro de texto com as ligações de descarga dos
  recursos dos registos públicos listados, para uso com um gestor de descargas como o `aria2c`.
- **regular layout** e **compact layout** alternam entre as duas disposições da lista.

### Criar um registo

Além da descoberta da missão, os registos podem ser criados manualmente, com o botão
**add new survey-related record** da página de detalhe da missão. O botão está desativado enquanto
a missão está em descoberta. O formulário tem os seguintes campos:

| Campo | Descrição |
|-------|-----------|
| Nome | Obrigatório. Identifica o registo e deve ser único entre os registos da missão. Até 100 caracteres; um registo válido requer pelo menos 5. |
| Descrição | Opcional. Resumo do conjunto de dados descrito pelo registo, até 500 caracteres. |
| Categoria | Obrigatório. Classifica o registo pelo tipo de dados que descreve. A lista contém as categorias definidas em [Categorias](#categorias). |
| Estádio | Obrigatório. Indica o estádio de processamento dos dados, como dados em bruto ou processados. A lista contém os estádios definidos em [Estádios](#estadios). |
| Extensão espacial | Longitude e latitude mínimas e máximas dos dados, em graus decimais, introduzidas como números ou desenhadas como um retângulo no mapa. Um registo válido requer uma extensão com área não nula. É substituída pela extensão extraída do ficheiro de dados do registo, quando esta é extraída. |
| Data de início, Data de fim | Opcional. Datas da primeira e da última aquisição dos dados. São substituídas pelas datas extraídas do ficheiro de dados do registo, quando ambas são extraídas. |
| Ligações | Opcional. Até 5 ligações para recursos externos relacionados com o registo. Cada ligação tem um URL, que deve usar `http` ou `https`, um tipo de media, uma relação e uma descrição de até 500 caracteres. |
| Recursos | Opcional. Até 20 ficheiros pertencentes ao registo, como descrito em [Trabalhar com recursos dos registos](#trabalhar-com-recursos-dos-registos). |
| Registos relacionados | Opcional. Até 5 relações com outros registos, como descrito em [Relacionar registos entre si](#relacionar-registos-entre-si). |

Quando o registo é criado, os metadados são extraídos do ficheiro do primeiro recurso de dados com
caminho relativo. A extensão espacial e a extensão temporal extraídas substituem as introduzidas no
formulário; os valores que não é possível extrair do ficheiro são mantidos tal como introduzidos.
Os outros metadados extraídos são apresentados na página de detalhe do registo. São depois geradas
pré-visualizações tal como para os registos descobertos, de acordo com a configuração de
descoberta de recursos que corresponde ao caminho do recurso.

### Atualizar um registo

O botão **edit** da página de detalhe do registo abre um formulário com os mesmos campos do
formulário de criação. O formulário lista apenas os recursos de dados do registo. O botão está
desativado enquanto o registo se encontra num estado transitório ou a sua missão está em
descoberta.

Quando o conjunto de caminhos dos recursos de dados é alterado, os metadados são extraídos
novamente do primeiro recurso de dados, tal como na criação, e as pré-visualizações do registo são
geradas novamente. Os outros metadados de uma extração anterior são substituídos pelos novos, ou
removidos quando não é possível extrair metadados. As atualizações que não alteram os caminhos dos
recursos de dados mantêm os valores introduzidos no formulário.

**Atualização em massa:** a ação **bulk update** da lista de registos da missão atualiza de uma
só vez os registos selecionados. O formulário apresenta o número de registos a atualizar. Cada um
dos seguintes grupos de campos só é aplicado quando a respetiva caixa de seleção está assinalada:

- **atualizar categoria**
- **atualizar estádio**
- **atualizar extensão espacial**
- **atualizar extensão temporal**
- **atualizar registos relacionados**, que substitui as relações existentes dos registos

Os registos num estado transitório não são atualizados. Uma atualização em massa não valida os
registos nem altera o seu estado.

### Eliminar um registo

O botão **delete...** da página de detalhe do registo elimina o registo após uma confirmação. A
eliminação de um registo elimina também os seus recursos e as suas relações com outros registos.
Os ficheiros do arquivo não são modificados. O botão está desativado enquanto o registo se
encontra num estado transitório ou a sua missão está em descoberta.

### Relacionar registos entre si

Um registo pode ser relacionado com até cinco outros registos, de qualquer missão ou projeto. Cada
relação é introduzida na secção **registos relacionados** do formulário do registo, com os
seguintes campos:

| Campo | Descrição |
|-------|-----------|
| Registo relacionado | O registo relacionado, selecionado entre as sugestões apresentadas durante a escrita do seu nome. |
| Relação | Obrigatório. Nome da relação, até 50 caracteres, por exemplo `derived from`. |

Os nomes das relações são texto livre. A página de detalhe do registo lista os registos com os
quais está relacionado, em **related to**, e os registos que estão relacionados com ele, em
**subject to**.

### Exportar um registo para o GeoNode

O botão **exportar para o GeoNode...** da página de detalhe de um registo carrega os dados do
registo no GeoNode, após uma confirmação. O botão é apresentado aos utilizadores com a função
`catalog-editor` ou `system-admin`, para os registos públicos com um recurso de dados num dos
formatos `.tif`, `.tiff`, `.gpkg`, `.geojson` ou `.shp`, que são os formatos suportados pelo
GeoNode. O registo está em exportação enquanto o carregamento decorre. A exportação repetida de um
registo substitui a exportação anterior. A página de detalhe do registo apresenta a ligação para o
recurso do GeoNode e a data da exportação.


## Trabalhar com recursos dos registos

Um recurso é um ficheiro pertencente a um registo. Existem dois tipos de recursos:

- Os **recursos de dados** referem-se a ficheiros do arquivo. Um registo tem normalmente um
  recurso de dados com os seus dados principais, e pode conter outros, por exemplo ficheiros
  auxiliares do mesmo conjunto de dados.
- Os **recursos derivados** são gerados pela aplicação a partir dos recursos de dados. É gerada
  uma imagem de pré-visualização para cada recurso de dados num formato suportado, que é usada
  como miniatura do registo nas listagens e apresentada sobre o mapa da página de detalhe do
  registo.

Os recursos são geridos na secção **recursos** do formulário do registo. Cada recurso de dados tem
os seguintes campos:

| Campo | Descrição |
|-------|-----------|
| Nome | Obrigatório. Identifica o recurso e deve ser único entre os recursos do registo. Até 100 caracteres. |
| Descrição | Opcional. Resumo do conteúdo do ficheiro, até 500 caracteres. |
| Tipo de media | Opcional. Tipo de media do ficheiro, usado para identificar o seu formato, por exemplo `image/tiff`. Quando vazio, é derivado da extensão do ficheiro, como `application/prs.ipma.<extensão>`. |
| Caminho relativo | Caminho do ficheiro no arquivo, relativo ao diretório da missão, por exemplo `s06-mbes/s05-processed-data/grid.tif`. Deve ser único entre os recursos da missão. Os metadados do registo são extraídos do ficheiro do seu primeiro recurso de dados com caminho relativo. |
| Ligações | Opcional. Até 5 ligações para recursos externos relacionados com o recurso. Cada ligação tem um URL, que deve usar `http` ou `https`, um tipo de media, uma relação e uma descrição de até 500 caracteres. |

Os recursos derivados não são apresentados no formulário e não podem ser editados. São
substituídos quando os caminhos dos recursos de dados do registo são alterados.

Os recursos de dados de um registo podem ser descarregados a partir da sua página de detalhe pelos
utilizadores que podem ver o registo. As shapefiles são descarregadas como um ficheiro zip que
contém o ficheiro `.shp` e os respetivos ficheiros auxiliares.


## Definições e tabelas auxiliares

As tabelas auxiliares são geridas a partir do menu **Settings** da barra superior, apresentado aos
utilizadores autenticados. Apenas os utilizadores com a função `catalog-editor` ou `system-admin`
podem criar, atualizar ou eliminar as suas entradas. Cada lista oferece uma pesquisa por nome, e
uma ação **edit** e uma ação **delete** para cada entrada. A eliminação de uma entrada requer uma
confirmação.

### Categorias

As categorias classificam os registos pelo tipo de dados que contêm, por exemplo dados
batimétricos ou sísmicos. Cada registo tem uma categoria, que pode ser usada para filtrar os
registos nas listagens de registos. As categorias são geridas em `/dataset-categories/`.

#### Criar uma categoria

O botão **Add new dataset category** abre um formulário com um único campo **Nome**. Os nomes
devem ser únicos.

#### Atualizar uma categoria

A ação **edit** da entrada de uma categoria abre um formulário com o seu campo **Nome**.

#### Eliminar uma categoria

A ação **delete** da entrada de uma categoria elimina a categoria. Os registos de uma categoria
eliminada são mantidos, sem categoria, e são apresentados como **categoria desconhecida**. Um
registo sem categoria não é válido até lhe ser novamente atribuída uma categoria.

### Estádios

Os estádios classificam os registos pelo estádio de processamento dos seus dados, por exemplo
dados em bruto ou dados processados. Cada registo tem um estádio, que pode ser usado para filtrar
os registos nas listagens de registos. Os estádios são geridos em `/workflow-stages/`.

#### Criar um estádio

O botão **Add new workflow stage** abre um formulário com um único campo **Nome**. Os nomes devem
ser únicos.

#### Atualizar um estádio

A ação **edit** da entrada de um estádio abre um formulário com o seu campo **Nome**.

#### Eliminar um estádio

A ação **delete** da entrada de um estádio elimina o estádio. Os registos de um estádio eliminado
são mantidos, sem estádio, e são apresentados como **estádio desconhecido**. Um registo sem
estádio não é válido até lhe ser novamente atribuído um estádio.

### Configurações de descoberta de recursos

As configurações de descoberta de recursos definem quais os ficheiros do diretório de uma missão
que são convertidos em registos por uma descoberta da missão, e com que categoria e estádio. São
geridas em `/asset-discovery-configurations/`.

#### Criar uma configuração de descoberta de recursos

O formulário **nova configuração de descoberta de recursos** tem os seguintes campos:

| Campo | Descrição |
|-------|-----------|
| Nome | Obrigatório. Identifica a configuração. Deve ser único. |
| Expressão regular do caminho relativo | Obrigatório. Padrão de caminho dos ficheiros abrangidos pela configuração, como descrito abaixo. |
| Tipo de media | Obrigatório. Tipo de media dos ficheiros abrangidos. |
| Categoria | Categoria dos registos criados para os ficheiros abrangidos. |
| Estádio | Estádio dos registos criados para os ficheiros abrangidos. |
| Gerar pré-visualizações | Indica se são geradas pré-visualizações para os recursos abrangidos pela configuração. |

A expressão regular do caminho relativo é um caminho relativo ao diretório da missão, cujos
segmentos são separados por `/`:

- Os segmentos iniciais sem caracteres de expressão regular formam um prefixo literal. A
  descoberta percorre apenas os diretórios abaixo deste prefixo.
- Cada um dos restantes segmentos é uma expressão regular que corresponde a um nome completo de
  diretório ou de ficheiro. O último segmento corresponde ao nome do ficheiro.
- Pode existir qualquer número de diretórios antes, entre ou depois dos diretórios correspondentes
  aos segmentos de expressão regular.
- Um padrão sem segmentos de expressão regular corresponde apenas ao caminho que designa.

Por exemplo, o padrão `s06-mbes/s02-raw-data/.*\.kmall` corresponde a todos os ficheiros com a
extensão `.kmall` abaixo do diretório `s06-mbes/s02-raw-data`, a qualquer profundidade.

Um ficheiro é atribuído à primeira configuração, por ordem alfabética do nome da configuração,
cujo padrão corresponde ao seu caminho. A mesma regra determina se são geradas pré-visualizações
para um recurso de dados, incluindo os recursos dos registos criados manualmente. Uma configuração
cujo padrão não é uma expressão regular válida é ignorada, e o seu nome é indicado no resumo da
descoberta.

#### Atualizar uma configuração de descoberta de recursos

A ação **edit** da entrada de uma configuração abre um formulário com os mesmos campos do
formulário de criação. As alterações aplicam-se às descobertas iniciadas posteriormente; os
registos existentes não são modificados.

#### Eliminar uma configuração de descoberta de recursos

A ação **delete** da entrada de uma configuração elimina a configuração. Os registos não mantêm
uma referência à configuração que os criou, pelo que a eliminação de uma configuração não modifica
nenhum registo. Os ficheiros abrangidos apenas por uma configuração eliminada não são encontrados
pelas descobertas posteriores.
