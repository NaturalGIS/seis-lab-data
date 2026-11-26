# Documentação do SeisLabData

O SeisLabData é uma aplicação web para a catalogação dos dados de levantamentos marinhos do IPMA. O catálogo está
organizado numa hierarquia de projetos, das missões realizadas no âmbito de cada projeto e dos registos que descrevem
os conjuntos de dados produzidos por cada missão. Os ficheiros de dados permanecem no sistema de ficheiros do arquivo,
enquanto o catálogo guarda os seus metadados, a sua localização no arquivo e pré-visualizações derivadas.

Os registos podem ser criados manualmente ou gerados pela descoberta de uma missão, que percorre o diretório da missão
no arquivo e extrai a extensão espacial, a extensão temporal e outros metadados dos ficheiros que encontra. Os
registos publicados são também disponibilizados através de uma [API STAC](user-guide.md#stac-api) e podem ser
exportados para o GeoNode.


<div class="grid cards" markdown>

-   :material-account-search:{ .lg .middle } __Utilizadores__

    ---

    Como consultar, pesquisar, criar e publicar projetos, missões e registos, e como descobrir o conteúdo das
    missões no arquivo.

    [:octicons-arrow-right-24: Guia do utilizador](user-guide.md)

-   :material-server-network:{ .lg .middle } __Administradores de sistemas__

    ---

    O ambiente de produção, a instalação do sistema, os seus componentes e a sua manutenção operacional, incluindo
    a gestão das contas de utilizador.

    [:octicons-arrow-right-24: Guia de administração do sistema](admin-guide.md)

-   :material-code-braces:{ .lg .middle } __Programadores__

    ---

    A configuração de um ambiente de desenvolvimento local, a arquitetura do sistema, o ambiente de testes e a
    escrita desta documentação.

    [:octicons-arrow-right-24: Guia de desenvolvimento](development.md)

    [:octicons-arrow-right-24: Guia do ambiente de testes](test-environment.md)

    [:octicons-arrow-right-24: Guia de escrita de documentação](writing-docs.md)

</div>

Esta documentação está disponível em português e em inglês, selecionável no menu de idioma da barra superior. Os
guias do utilizador, de administração e de desenvolvimento podem também ser descarregados em formato PDF:

- [:material-file-pdf-box: Guia do utilizador](assets/documents/seis-lab-data-user-guide.pdf)
- [:material-file-pdf-box: Guia de administração do sistema](assets/documents/seis-lab-data-administration-guide.pdf)
- [:material-file-pdf-box: Guia de desenvolvimento](assets/documents/seis-lab-data-development-guide.pdf)
