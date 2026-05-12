# PRD: Servidor MCP HTTP Interno para Governança de IA

## 1. Introduction/Overview

Construir um servidor MCP HTTP interno que funcione como **fonte de verdade corporativa** para agentes de IA e mantenedores técnicos.  
O produto terá dois lados:

1. **Lado Agentes:** responder perguntas em linguagem natural sobre libs, versões, padrões e práticas recomendadas; além de expor tools de verificação de conformidade de código, dependências e infraestrutura.
2. **Lado Mantenedores:** permitir ingestão e gestão simples de conhecimento técnico (PDF, Markdown, repositórios Git e páginas web/Confluence), com indexação vetorial para recuperação semântica.

Stack mandatória da v1: **Python + FastMCP (HTTP)**, **Qdrant** como banco vetorial, **modelo de embeddings self-hosted** (ex.: BGE-M3), **Docker Compose**, **uv** para gestão de dependências e **MkDocs** para documentação.

## 2. Goals

- Entregar um MCP HTTP interno funcional para agentes e mantenedores na v1.
- Centralizar políticas e padrões de engenharia em uma base consultável e auditável.
- Permitir ingestão multi-fonte com pipeline padronizado e rastreável.
- Expor tools MCP para análise de conformidade de código, libs e infra com resultados claros.
- Garantir documentação operacional e técnica completa (README + MkDocs).

## 3. User Stories

### US-001: Inicializar servidor MCP HTTP em Python
**Description:** As a platform engineer, I want a Python MCP HTTP server baseline so that all agents can consume a single governance endpoint.

**Acceptance Criteria:**
- [ ] Projeto inicial criado com `uv` (ambiente, dependências e lockfile)
- [ ] Servidor implementado com **FastMCP** e transporte **HTTP** como padrão
- [ ] Endpoint MCP HTTP funcional com healthcheck e metadata do serviço
- [ ] Estrutura de módulos separa claramente runtime MCP, domínio e adapters
- [ ] Dockerfile e `docker-compose.yml` sobem o serviço localmente
- [ ] Typecheck/lint passes

### US-002: Disponibilizar Q&A de governança para agentes
**Description:** As an AI agent, I want to ask natural language questions about approved libs, versions and coding patterns so that I can align generated code with company standards.

**Acceptance Criteria:**
- [ ] Tool MCP de consulta semântica retorna resposta + fontes citadas
- [ ] Perguntas sobre “posso usar lib X?” e “qual versão de Y?” retornam política vigente
- [ ] Resposta inclui nível de confiança e data/versão da política aplicada
- [ ] Falta de evidência é retornada explicitamente (sem resposta silenciosa)
- [ ] Typecheck/lint passes

### US-003: Expor tools MCP de conformidade técnica
**Description:** As an AI agent, I want compliance tools for code/libs/infra so that I can validate if outputs are aligned with internal governance.

**Acceptance Criteria:**
- [ ] Tool de conformidade de libs valida pacote/versão contra catálogo aprovado
- [ ] Tool de conformidade de código avalia aderência a padrões definidos
- [ ] Tool de conformidade de infraestrutura avalia requisitos mínimos declarados (ex.: imagens base, portas, variáveis sensíveis)
- [ ] Resultado padronizado com status (`compliant`, `warning`, `non_compliant`) e justificativas
- [ ] Typecheck/lint passes

### US-004: Implementar ingestão multi-fonte para mantenedores
**Description:** As a maintainer, I want to ingest Markdown, PDF, Git repositories and web/Confluence pages so that governance knowledge stays current and searchable.

**Acceptance Criteria:**
- [ ] Pipeline aceita os quatro tipos de fonte na v1
- [ ] Cada fonte é normalizada para chunks com metadata (origem, timestamp, versão)
- [ ] Erros por fonte são reportados com causa e item afetado
- [ ] Processo de ingestão permite execução incremental (novos/alterados)
- [ ] Fonte Confluence na v1 usa **fluxo de export + ingest** (sem crawler e sem integração direta via API)
- [ ] Typecheck/lint passes

### US-005: Gerir catálogo de libs, versões e padrões
**Description:** As a maintainer, I want to manage approved libraries, versions and coding standards so that agents receive authoritative and updated guidance.

**Acceptance Criteria:**
- [ ] Existe modelo de dados para catálogo de libs/versões/status (aprovada, restrita, proibida)
- [ ] Existe modelo de dados para padrões de código e guidelines por contexto
- [ ] Atualizações ficam versionadas e auditáveis (quem alterou, quando, motivo)
- [ ] Consultas MCP usam sempre a versão ativa mais recente por padrão
- [ ] Typecheck/lint passes

### US-006: Persistir embeddings em banco vetorial
**Description:** As a platform engineer, I want vector storage for indexed content so that retrieval quality remains high across varied technical sources.

**Acceptance Criteria:**
- [ ] Camada vetorial usa **Qdrant** como backend oficial da v1
- [ ] Serviço de embeddings é **self-hosted** (container dedicado) com versão do modelo registrada no metadata
- [ ] Estratégia de chunking e embeddings definida por tipo de fonte
- [ ] Busca híbrida (semântica + filtros por metadata) disponível para Q&A
- [ ] Reindexação seletiva por fonte ou coleção
- [ ] Typecheck/lint passes

### US-008: Proteger tools MCP com autenticação/autorização corporativa
**Description:** As a security engineer, I want authenticated and authorized access to MCP tools so that only approved internal clients can perform governed operations.

**Acceptance Criteria:**
- [ ] Autenticação via **OIDC Client Credentials** com emissão/validação de JWT
- [ ] Autorização via **RBAC por escopo** (consulta, conformidade, ingestão, administração)
- [ ] Requisições sem token válido retornam erro explícito e auditável
- [ ] Requisições autenticadas sem escopo necessário retornam erro explícito e auditável
- [ ] Typecheck/lint passes

### US-009: Definir política de retenção documental da v1
**Description:** As a maintainer, I want a clear retention policy for indexed documents so that storage and restoration behavior are predictable.

**Acceptance Criteria:**
- [ ] Política definida como **versão ativa + snapshots periódicos**
- [ ] Periodicidade mínima de snapshot definida e documentada (operação)
- [ ] Processo de restauração a partir de snapshot documentado no MkDocs
- [ ] Typecheck/lint passes

### US-007: Publicar documentação operacional e de produto
**Description:** As a maintainer, I want complete docs so that onboarding and operation are predictable and repeatable.

**Acceptance Criteria:**
- [ ] README cobre setup rápido com `uv` e Docker Compose
- [ ] MkDocs inclui arquitetura, ingestão, operação e uso das tools MCP
- [ ] Guia de troubleshooting para falhas comuns de ingestão e consulta
- [ ] Guia de governança de atualização de políticas/catalogos
- [ ] Typecheck/lint passes

## 4. Functional Requirements

1. **FR-1:** O sistema deve expor servidor MCP HTTP em Python usando **FastMCP** com transporte HTTP padrão e endpoint de saúde.
2. **FR-2:** O sistema deve oferecer tool MCP de Q&A em linguagem natural com resposta rastreável por fonte.
3. **FR-3:** O sistema deve oferecer tool MCP para validação de uso de biblioteca e versão.
4. **FR-4:** O sistema deve oferecer tool MCP para validação de conformidade de padrões de código.
5. **FR-5:** O sistema deve oferecer tool MCP para validação de conformidade de infraestrutura declarada.
6. **FR-6:** O sistema deve suportar ingestão de Markdown, PDF, repositórios Git e páginas web/Confluence.
7. **FR-7:** O sistema deve gerar embeddings via serviço **self-hosted** e armazená-los no **Qdrant** com metadata de origem/versionamento.
8. **FR-8:** O sistema deve permitir atualização incremental e reprocessamento seletivo de fontes.
9. **FR-9:** O sistema deve manter catálogo versionado de libs, versões e padrões com trilha de auditoria.
10. **FR-10:** O sistema deve retornar resultados de conformidade em formato padronizado com severidade e evidências.
11. **FR-11:** O sistema deve ser empacotado para execução via Docker Compose.
12. **FR-12:** O sistema deve usar `uv` como gerenciador oficial de dependências e ambiente.
13. **FR-13:** O sistema deve disponibilizar documentação completa em MkDocs e README.
14. **FR-14:** Decisões de bibliotecas e integrações externas devem ser embasadas por pesquisa de documentação atual via Context7.
15. **FR-15:** O sistema deve autenticar chamadas MCP com **OIDC Client Credentials + JWT**.
16. **FR-16:** O sistema deve aplicar **RBAC por escopo** em todas as tools MCP.
17. **FR-17:** A integração Confluence da v1 deve ocorrer por **export + ingest**.
18. **FR-18:** A política de retenção documental da v1 deve ser **versão ativa + snapshots periódicos**, com restauração documentada.

## 5. Non-Goals (Out of Scope)

- Multi-tenant na v1.
- Painel web completo de administração na v1 (gestão pode ser via API/CLI interna).
- Execução automática de remediação (auto-fix) de não conformidades na v1.
- Suporte a todas as fontes corporativas possíveis além das 4 definidas (Markdown, PDF, Git, web/Confluence).
- SLA corporativo avançado (HA multi-região) na v1.
- Integração Confluence direta via API/crawler na v1.

## 6. Design Considerations

- Priorizar contratos MCP claros e estáveis para consumo por diferentes agentes.
- Respostas para agentes devem sempre explicitar fonte, versão da política e justificativa.
- Modelo de saída das tools de conformidade deve ser uniforme para facilitar automação downstream.

## 7. Technical Considerations

- Linguagem e runtime: Python 3.11+ com FastMCP.
- Dependências e ambientes: `uv` como padrão obrigatório de projeto.
- Infra local/padrão: Docker + Docker Compose.
- Armazenamento semântico: Qdrant.
- Embeddings: modelo self-hosted (ex.: BGE-M3) em serviço/container dedicado.
- Ingestão:
  - PDF: extração de texto + metadata de origem.
  - Markdown: parsing preservando hierarquia de seções.
  - Git: leitura de docs e arquivos alvo por repositório/ref.
  - Web: coleta controlada com política de atualização.
  - Confluence: exportação (HTML/PDF/Markdown exportado) + ingestão.
- Segurança:
  - OIDC Client Credentials para autenticação de clientes internos.
  - JWT para propagação de identidade/scopes.
  - RBAC por escopo para autorização por tool.
- Retenção documental:
  - Manter somente versão ativa indexada.
  - Gerar snapshots periódicos para recuperação.
- Observabilidade mínima: logs estruturados de consulta, ingestão e conformidade.
- Documentação obrigatória com MkDocs e versão publicada internamente.
- Seleção de libs/frameworks deve ser validada com Context7 antes de consolidação.

## 8. Success Metrics

- Pelo menos **90%** das perguntas alvo de agentes sobre libs/versões/padrões respondidas com fonte rastreável.
- Cobertura de conformidade disponível para os 3 eixos na v1: código, dependências e infraestrutura.
- Ingestão incremental com taxa de sucesso **>= 95%** por execução (itens processados sem erro).
- Onboarding de mantenedor com setup funcional seguindo apenas README + MkDocs em ambiente Docker Compose.
- Redução de inconsistência entre respostas de diferentes agentes para a mesma pergunta de governança (mesma política/versionamento retornados).
- **100%** das chamadas MCP autenticadas e autorizadas por escopo (sem bypass).

## 9. Decisões Fechadas

1. **Banco vetorial (v1):** Qdrant.
2. **Framework MCP HTTP em Python:** FastMCP.
3. **Embeddings (v1):** modelo self-hosted (ex.: BGE-M3).
4. **AuthN/AuthZ interno:** OIDC Client Credentials + JWT + RBAC por escopo.
5. **Retenção/versionamento de documentos:** versão ativa + snapshots periódicos.
6. **Integração Confluence (v1):** export + ingest.

### 9.1 Notas de implementação derivadas das decisões

- **Qdrant:** usar collections com payload index para filtros por metadata (fonte, versão, timestamp, domínio).
- **FastMCP:** padronizar transporte HTTP para integração interna entre agentes.
- **Embeddings self-hosted:** definir serviço interno dedicado (container) e contrato de versionamento de modelo.
- **OIDC + RBAC:** mapear escopos mínimos por tool MCP (consulta, conformidade, ingestão, administração).
- **Versão ativa + snapshots:** explicitar periodicidade e política de restauração no guia operacional.
- **Confluence export + ingest:** formalizar formato aceito (HTML/PDF/Markdown exportado) e janela de atualização.
