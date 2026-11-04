# Tasks: Connecteur de recherche MPI (openIMIS → CHC via openHIM)

**Feature**: `feature-38373`
**Input**: `specs/38373-mpi-search-connector/spec.md` (validée le 2026-11-04)
**Prerequisites**: spec validée, tickets #38374 (client), #38375 (mapping/création), #38376 (accroche/flag)
**Tests**: obligatoires (unitaires + base + concurrence), livrés dans le même ticket que le code.

## Contradictions à trancher (spec vs tickets)

1. **Group / famille existante** — la spec dit « un seul Patient, jamais de Group, une Family dont l'assuré est le chef et le seul membre ». #38374 parle de « Patient (et Group si nécessaire) » ; #38375 parle de « Group → Family », de « liens de parenté issus du Group » et de « rattachement à une famille existante ». → aligner #38374/#38375 sur la spec.
2. **Rejeu / disjoncteur** — la spec (section Robustesse de la version revue) dit « une seule tentative, pas de rejeu, pas de disjoncteur ». #38374 demande « un seul rejeu, disjoncteur ». → trancher et aligner.
3. **Flag d'activation** — la spec finale ne contient plus de FR sur le flag ; l'EPIC et #38376 exigent `MPI_FALLBACK_ENABLED` (off par défaut). → ajouter un FR/assumption à la spec ou acter le flag comme contrainte de #38376.
4. **CHC indisponible** — spec FR-012 : erreur explicite distincte de « introuvable ». #38376 : « réponse identique à l'existant ». → aligner #38376 sur FR-012.
5. **Clé d'idempotence** — spec FR-011 : idempotence par CHFID actif (pas de table d'identifiant externe). #38375 : « stockage de l'identifiant CHC et contrainte d'unicité (clé = identifiant FHIR) ». → aligner #38375 ; la concurrence se règle par verrou consultatif + re-check.
6. **`audit_user_id`** — spec FR-009 : `TechnicalUser.id_for_audit`, repli `-1` ; US2 teste `-1` en dur. → tester `TechnicalUser.id_for_audit`, pas la constante.
7. **Traçabilité vs données personnelles** — US2 veut voir le CHFID recherché ; FR-013 interdit les données personnelles en log. → CHFID dans la transaction openHIM (infra), hash tronqué dans les logs applicatifs.
8. **Statut de la spec** — `Status: Draft` alors qu'elle est validée. → passer à `Validated`.
9. **Mécanisme de création de Family** — FR-006 dit « mécanisme existant » sans le nommer. → utiliser `create_insuree_family` (ou `InsureeService.create_or_update(create_family=True)`).
10. **Localisation** — FR-008 ne couvre pas le cas de plusieurs `Location` actives portant `05BAT06V`. → refuser (anomalie) si 0 ou >1.
11. **Flag « sans redéploiement »** — #38376 : un flag lu au démarrage nécessite un redémarrage. → préciser « sans redéploiement, redémarrage accepté ».
12. **CHFID historique** — l'idempotence ne porte que sur les CHFID actifs ; un CHFID présent uniquement en historique sera recréé (doublon historique). → assumer ou préciser.

---

## Phase 1 — Setup (infrastructure partagée)

- [ ] **T001** [#38374/#38376] Ajouter la configuration du connecteur dans `insuree/apps.py` (`DEFAULT_CFG`) : `mpi_fallback_enabled` (False), `mpi_base_url`, `mpi_auth_user`, `mpi_auth_password`, `mpi_timeout_connect` (3 s), `mpi_timeout_read` (7 s), `mpi_total_timeout` (10 s), `mpi_default_location_code` (`05BAT06V`), `mpi_audit_user`.
- [ ] **T002** [#38374] Créer `insuree/mpi/` : `__init__.py`, `exceptions.py` (`MpiError`, `MpiUnavailable`, `MpiAmbiguous`, `MpiInvalidPayload`).
- [ ] **T003** [#38376] Test : flag désactivé → aucun appel réseau, comportement inchangé.

## Phase 2 — Foundational (bloquant)

- [ ] **T004** [#38374] `insuree/mpi/client.py` : `search_patient(identifier) -> Bundle | None`, basic-auth, timeouts 3/7/10 s, gestion 200/404/5xx/réponse invalide.
- [ ] **T005** [#38374] Tests client (HTTP simulé) : auth, 200, 404, 500, timeout, JSON invalide, date limite totale.
- [ ] **T006** [#38375] `insuree/mpi/mapper.py` : `to_insuree_dto(patient) -> dict` (nom, prénoms, sexe, date de naissance obligatoires ; `telecom`, `address`, `deceased`).
- [ ] **T007** [#38375] Tests mapper : mapping complet, champs manquants (refus), genre, date.
- [ ] **T008** [#38375] `insuree/mpi/location.py` : résoudre `05BAT06V` → `Location.id` actif ; refus si 0 ou >1.
- [ ] **T009** [#38375] Tests localisation : trouvée, absente, multiple.
- [ ] **T010** [#38375] Helper `get_mpi_audit_user_id()` → `TechnicalUser.id_for_audit` (repli `-1`), sans exiger la permission de création.
- [ ] **T011** [#38374] Commande `manage.py mpi_check <chfid>` : appel CHC, résultat exploitable, logs sans donnée personnelle.

## Phase 3 — User Story 1 (P1) : retrouver et créer

- [ ] **T012** [#38375] `insuree/mpi/service.py` : `get_or_create_from_bundle(bundle, chf_id)` ; transaction atomique ; `chf_id` = CHFID recherché ; `Insuree` créé via `InsureeService.create_or_update(..., create_family=True)` / `create_insuree_family` ; `Family` avec localisation résolue.
- [ ] **T013** [#38375] Idempotence/concurrence : verrou `pg_advisory_xact_lock(hashtext('mpi:' || chf_id))`, re-check `Insuree` actif après verrou, relecture sur `IntegrityError`. Pas d'index unique sur `chf_id`.
- [ ] **T014** [#38375] Cas de réponse : 0 patient → `None` ; 1 → création ; >1 → `MpiAmbiguous` (aucune création) ; panne/invalide → `MpiUnavailable`/`MpiInvalidPayload` (aucune création).
- [ ] **T015** [#38375] Tests service : Insuree + Family réellement créés, chef + seul membre, `chf_id`, localisation, rollback, idempotence.
- [ ] **T016** [#38375] Tests concurrence (`TransactionTestCase`, 2 connexions) : 2 créations simultanées → 1 Insuree / 1 Family ; 3e appel → existant.
- [ ] **T017** [#38376] Accroche `insuree/schema.py::resolve_insurees` : `chfId` exact, résultat local vide, flag actif → service puis ré-exécution locale ; pas de déclenchement sur listes/recherches par nom ; pas de récursion.
- [ ] **T018** [#38376] Tests resolver : flag off (aucun appel), local trouvé (aucun appel), vide + 1 (création + retour), vide + 0, >1, panne, non-régression enquête.
- [ ] **T019** [#38376] Test de bout en bout avec `chc_mock.py` sur l'environnement de test.

## Phase 4 — User Story 2 (P2) : traçabilité

- [ ] **T020** [#38376] Journalisation sans PII : corrélation + hash tronqué (8 caractères) du CHFID, aucun corps requête/réponse.
- [ ] **T021** [#38376] Propager l'identifiant de transaction openHIM dans les logs et la réponse d'erreur.
- [ ] **T022** [#38376] Tests logs : aucun CHFID en clair, aucune donnée patient.

## Phase 5 — Polish

- [ ] **T023** [#38373] Passer `Status` de la spec à `Validated` et corriger les contradictions 1 à 12 (section ci-dessus).
- [ ] **T024** [#38373] Mettre à jour les descriptions de #38374/#38375/#38376 (Group, rejeu, clé d'idempotence, erreur CHC indisponible).
- [ ] **T025** [#38376] Non-régression flag off : suite existante + tests dédiés.
- [ ] **T026** PR, revue, CI verte ; démonstration de bout en bout avant le 20/11.

## Dependencies

- T004–T011 avant T012–T019.
- T012–T017 avant T018–T019.
- T020–T022 en parallèle après T012.
- T023–T024 avant de lancer l'implémentation des tickets 2/4 à 4/4.

## Parallel Execution Examples

- T004 (client), T006 (mapper), T008 (localisation), T010 (audit) en parallèle.
- T005, T007, T009 (tests) en parallèle avec leurs composants.
- T020–T022 en parallèle avec T017–T019.

## Implementation Strategy

MVP = User Story 1 (T001–T019). User Story 2 ensuite. `MPI_FALLBACK_ENABLED` désactivé par défaut ; comportement strictement identique quand il est off.
