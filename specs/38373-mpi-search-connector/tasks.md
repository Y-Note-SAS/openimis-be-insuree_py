# Tasks: Connecteur de recherche MPI (openIMIS → CHC via openHIM)

**Feature**: `feature-38373`
**Input**: `specs/38373-mpi-search-connector/spec.md` (validée le 2026-11-04)
**Prerequisites**: spec validée, tickets #38374 (client), #38375 (mapping/création), #38376 (accroche/flag)
**Validation des tasks**: dans **#38374** (ticket de travail courant)
**Tests**: obligatoires (unitaires + base + concurrence), livrés dans le même ticket que le code.

## Répartition par ticket

| Ticket | Périmètre | Tâches |
|---|---|---|
| **#38374** (2/4) | Client openHIM + commande de diagnostic | T001–T007 |
| **#38375** (3/4) | Mapping + création Insuree + Family idempotente | T008–T016 |
| **#38376** (4/4) | Accroche GraphQL + flag + traçabilité | T017–T024 |
| Transverse | Spec, tickets, DoD | T025–T026 |

## Décisions actées (alignées sur la spec)

- Un seul Patient renvoyé par le CHC, **aucun Group** ; aucune famille existante réutilisée.
- Une Family par Patient, dont il est le chef et le **seul membre**, via `create_insuree_family` (non modifié).
- `chf_id` = CHFID recherché (identifiant MPI) ; localisation fixe `05BAT06V` → `Location.id`.
- `audit_user_id` = `TechnicalUser.id_for_audit` (repli `-1`), sans permission de création.
- Idempotence par CHFID **actif** : verrou `pg_advisory_xact_lock` + re-check ; pas de table d'identifiant externe, pas d'index unique sur `chf_id`.
- Une seule tentative réseau : pas de rejeu automatique, pas de disjoncteur.
- CHC indisponible : erreur explicite distincte de « CHFID introuvable », aucune création.
- Flag `MPI_FALLBACK_ENABLED` désactivé par défaut.

---

## 2/4 — #38374 : Client openHIM + diagnostic

- [ ] **T001** Config client dans `insuree/apps.py` (`DEFAULT_CFG`) : `mpi_base_url`, `mpi_auth_user`, `mpi_auth_password`, `mpi_timeout_connect` (3 s), `mpi_timeout_read` (7 s), `mpi_total_timeout` (10 s), `mpi_patient_path` (défaut `/api/fhir/Patient`).
- [ ] **T002** Créer `insuree/mpi/` : `__init__.py`, `exceptions.py` (`MpiError`, `MpiUnavailable`, `MpiAmbiguous`, `MpiInvalidPayload`).
- [ ] **T003** `insuree/mpi/client.py` : `search_patient(identifier) -> Bundle | None`, basic-auth, timeouts 3/7/10 s, gestion 200/404/5xx/réponse invalide/Bundle vide.
- [ ] **T004** Tests client (HTTP simulé) : auth, 200, 404, 500, timeout, JSON invalide, date limite totale.
- [ ] **T005** Commande `manage.py mpi_check <chfid>` : appel CHC, résultat exploitable, aucun appelant dans le chemin de requête.
- [ ] **T006** Tests commande : patient trouvé, 0 patient, 404, 500, timeout.
- [ ] **T007** Logs client/commande : corrélation + hash tronqué (8 caractères) du CHFID, aucun corps requête/réponse.

## 3/4 — #38375 : Mapping + création idempotente

- [ ] **T008** Config création dans `insuree/apps.py` : `mpi_default_location_code` (`05BAT06V`), `mpi_audit_user`.
- [ ] **T009** `insuree/mpi/mapper.py` : `to_insuree_dto(patient) -> dict` (nom, prénoms, date de naissance, sexe, téléphone, adresse, état matrimonial, décès).
- [ ] **T010** Tests mapper : mapping complet, champs manquants (refus), genre, date.
- [ ] **T011** `insuree/mpi/location.py` : résoudre `05BAT06V` → `Location.id` actif ; refus si 0 ou >1.
- [ ] **T012** Tests localisation : trouvée, absente, multiple.
- [ ] **T013** Helper `get_mpi_audit_user_id()` → `TechnicalUser.id_for_audit` (repli `-1`).
- [ ] **T014** `insuree/mpi/service.py` : `get_or_create_from_bundle(bundle, chf_id)` ; transaction atomique ; `chf_id` = CHFID recherché ; `Insuree` + `Family` via `create_insuree_family` ; localisation résolue.
- [ ] **T015** Idempotence/concurrence : verrou `pg_advisory_xact_lock(hashtext('mpi:' || chf_id))`, re-check du CHFID actif après verrou, relecture sur `IntegrityError`.
- [ ] **T016** Tests service : création réelle, chef + seul membre, localisation, rollback, idempotence, concurrence (2 connexions), 0/1/>1 patient, panne.

## 4/4 — #38376 : Accroche GraphQL + flag + traçabilité

- [ ] **T017** Config flag dans `insuree/apps.py` : `mpi_fallback_enabled` (`False` par défaut).
- [ ] **T018** Accroche `insuree/schema.py::resolve_insurees` : `chfId` exact, résultat local vide, flag actif → service puis ré-exécution locale ; pas de déclenchement sur listes/recherches par nom ; pas de récursion.
- [ ] **T019** Tests resolver : flag off (aucun appel), local trouvé (aucun appel), vide + 1 (création + retour), vide + 0, >1, panne, non-régression enquête.
- [ ] **T020** Test de bout en bout avec `chc_mock.py` sur l'environnement de test.
- [ ] **T021** Traçabilité : identifiant de transaction openHIM dans les logs et la réponse d'erreur ; aucune donnée personnelle.
- [ ] **T022** Tests logs : aucun CHFID en clair, aucune donnée patient.
- [ ] **T023** Non-régression flag off : suite existante + tests dédiés.
- [ ] **T024** PR, revue, CI verte pour #38376.

## Transverse

- [ ] **T025** Passer `Status` de la spec à `Validated` et pointer les tasks validées dans #38374.
- [ ] **T026** Vérifier la DoD de l'EPIC (#38352) : tests dans le même ticket, PR mergée, flag off = comportement inchangé.

## Dependencies

- T001–T007 (#38374) avant T008–T016 (#38375).
- T008–T016 (#38375) avant T017–T024 (#38376).
- T019–T020 après T018 ; T021–T022 en parallèle avec T019–T020.
- Validation des tasks (T025) dans #38374 avant de démarrer T008.

## Parallel Execution Examples

- T003 (client), T009 (mapper), T011 (localisation) peuvent être préparés en parallèle, mais T009–T011 ne sont livrés qu'en #38375.
- T004, T006, T010, T012 (tests) en parallèle avec leurs composants.
- T021–T022 en parallèle avec T019–T020.

## Implementation Strategy

MVP = #38374 (client + diagnostic), puis #38375 (mapping + création), puis #38376 (accroche + flag). `MPI_FALLBACK_ENABLED` reste off jusqu'à la démonstration de bout en bout.
