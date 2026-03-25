# Referência de dados

Referência rápida para as dimensões do modelo de dados utilizadas para classificar conjuntos
de dados no arquivo.

## Tipos de domínio

| Código | Tipo de domínio | Descrição |
|--------|-----------------|-----------|
| D1 | Geofísico | Dados de deteção remota e levantamentos acústicos (batimetria, backscatter, sísmica, magnetómetro/gradiómetro) |
| D2 | Geotécnico | Dados de amostragem física e ensaios in-situ (amostras de sedimentos superficiais, núcleos, testes CPT) |

## Categorias de dados

| Código | Categoria | Domínio |
|--------|-----------|---------|
| C1 | Batimetria | Geofísico |
| C2 | Backscatter | Geofísico |
| C3 | Sísmica | Geofísico |
| C4 | Magnetómetro/gradiómetro | Geofísico |
| C5 | Amostras de sedimentos superficiais | Geotécnico |
| C6 | Núcleos | Geotécnico |
| C7 | Testes CPT | Geotécnico |

## Fases do fluxo de trabalho

| Código | Fase | Descrição |
|--------|------|-----------|
| S1 | Dados em bruto | Dados não processados tal como adquiridos pelo instrumento |
| S2 | Controlo de qualidade | Dados com artefactos identificados ou removidos |
| S3 | Dados processados | Dados processados em produtos derivados (grelhas, mosaicos) |
| S4 | Dados interpretados | Produtos finais com interpretação geológica ou geofísica |

## Matriz formato-categoria

Indica quais formatos de ficheiro aparecem em que combinações de categoria e fase. Consulte
[Formatos suportados](supported-formats.pt.md) para descrições detalhadas dos formatos.

### Batimetria (C1)

| Formato | Em bruto (S1) | CQ (S2) | Processados (S3) | Interpretados (S4) |
|---------|---------------|---------|-------------------|---------------------|
| KMALL | Principal | | | |
| XYZ | Principal | Principal | | Secundário |
| CSV | Principal | Principal | | Secundário |
| NetCDF | | | Principal | Principal |
| GeoTIFF | | | Principal | Principal |
| CSAR | | | Principal | |
| Float Grid (.flt) | | | Secundário | Principal/Secundário |
| ASCII Grid (.asc) | | | | Principal |
| Projeto HIPS | | | Principal | |
| Shapefile | Secundário | Secundário | Secundário | Secundário |
| GeoJSON | | | Secundário | Secundário |
| GeoPackage | | | Secundário | Secundário |
| KML/KMZ | | | | Secundário |
| File Geodatabase | Secundário | Secundário | Secundário | Principal/Secundário |
| XLS | Secundário | Secundário | Secundário | |

### Backscatter (C2)

| Formato | Em bruto (S1) | CQ (S2) | Processados (S3) | Interpretados (S4) |
|---------|---------------|---------|-------------------|---------------------|
| KMALL | Principal | | | |
| XYZ | Principal | | | Principal |
| CSV | Principal | | | Principal |
| NetCDF | | | Principal | Principal |
| GeoTIFF | | Principal | Principal | Principal |
| CSAR | | | Principal | |
| Float Grid (.flt) | | | | Principal |
| ASCII Grid (.asc) | | | | Principal |
| GeoJSON | | | Secundário | Secundário |
| GeoPackage | | | Secundário | Secundário |
| KML/KMZ | | | | Secundário |
| File Geodatabase | Secundário | Secundário | Secundário | Principal/Secundário |

### Sísmica (C3)

| Formato | Em bruto (S1) | CQ (S2) | Processados (S3) | Interpretados (S4) |
|---------|---------------|---------|-------------------|---------------------|
| SEG-Y | Principal | | | |
| JSF | Principal | | | |
