# Feature Specification: Connecteur de recherche MPI (openIMIS → CHC via openHIM)

**Feature Branch**: `feature-38373`

**Created**: 2026-11-03

**Status**: Draft

**Input**: Redmine #38373 (parent #38352), cadre Phase 1 du 23/10 : « Développement d'un connecteur de recherche patient/groupe en temps réel dans openIMIS, vers le MPI du CHC via openHIM ».

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Retrouver au MPI un assuré absent localement (Priority: P1)

Un agent saisit dans l'enquête un CHFID qui n'existe pas encore dans openIMIS-CSU. Ce CHFID est l'identifiant MPI attribué par le CHC. openIMIS doit interroger le CHC via openHIM, récupérer le Patient, puis créer l'assuré et sa famille dans openIMIS, afin que l'agent puisse poursuivre sans recréer une fiche en doublon.

**Why this priority**: C'est le seul développement inclus au contrat Phase 1. Sans ce flux, un patient connu du MPI mais pas encore importé ne peut pas être pris en charge.

**Independent Test**: Saisir dans l'enquête un CHFID présent au CHC et absent d'openIMIS, puis vérifier que la fiche est créée et affichée, avec une seule Family dont l'assuré est le chef et le seul membre.

**Acceptance Scenarios**:

1. **Given** un CHFID absent localement mais présent au CHC, **When** l'agent lance l'enquête, **Then** openIMIS appelle openHIM, récupère un Patient, crée l'Insuree et sa Family, et affiche la fiche.
2. **Given** un CHFID déjà présent localement, **When** l'agent lance l'enquête, **Then** la fiche locale est affichée et aucun appel réseau n'est effectué.
3. **Given** un CHFID absent localement et au CHC, **When** l'agent lance l'enquête, **Then** le message « CHFID introuvable » est affiché et aucune fiche n'est créée.
4. **Given** le CHC indisponible (timeout, 5xx, réponse invalide), **When** l'agent lance l'enquête, **Then** un message d'erreur explicite est affiché, distinct de « introuvable », et aucune fiche n'est créée.
5. **Given** un Patient CHC sans nom, prénoms, sexe ou date de naissance, **When** openIMIS tente la création, **Then** la création est refusée et aucune valeur par défaut n'est utilisée.
6. **Given** un CHFID déjà créé lors d'une enquête précédente, **When** l'agent relance l'enquête, **Then** la fiche existante est renvoyée sans nouvelle création.
7. **Given** une réponse du CHC contenant plus d'un Patient, **When** openIMIS traite la réponse, **Then** une anomalie est tracée et aucune fiche n'est créée.

### User Story 2 - Tracer et expliquer la création d'une fiche (Priority: P2)

Un administrateur doit pouvoir expliquer pourquoi une fiche a été créée automatiquement : quel CHFID a été recherché, à quel moment, et avec quelle transaction openHIM. La création ne doit pas être anonyme.

**Why this priority**: La création est déclenchée par un agent qui n'a pas la permission de création ; la traçabilité est la contrepartie de ce choix.

**Independent Test**: Après un import, retrouver la transaction correspondante dans la console openHIM et vérifier que la fiche porte `audit_user_id` = -1.

**Acceptance Scenarios**:

1. **Given** un import réussi, **When** l'administrateur consulte la console openHIM, **Then** la transaction de recherche Patient est visible avec son statut.
2. **Given** une fiche créée par le connecteur, **When** l'administrateur consulte l'audit de la fiche, **Then** `audit_user_id` vaut `-1`, valeur par défaut de l'utilisateur technique.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Le système DOIT déclencher la recherche MPI lorsqu'une enquête par CHFID, en correspondance exacte, ne trouve aucun assuré localement.
- **FR-002**: Le système NE DOIT effectuer aucun appel réseau lorsque l'assuré existe localement.
- **FR-003**: Le système DOIT interroger le CHC via openHIM avec `GET <mpi_patient_path>?identifier=<CHFID>` (chemin configurable dans la configuration backend, défaut `/api/fhir/Patient`), en lecture seule.
- **FR-004**: Le système NE DOIT jamais écrire vers le CHC.
- **FR-005**: Si le CHC renvoie zéro Patient, le système DOIT afficher « CHFID introuvable » et ne rien créer.
- **FR-006**: Si le CHC renvoie un Patient, le système DOIT créer l'Insuree avec `chf_id` = CHFID recherché, puis une Family dont cet Insuree est le chef et le seul membre, via le mécanisme de création de famille existant, sans le modifier.
- **FR-007**: Si le CHC renvoie plus d'un Patient, le système DOIT refuser la création, tracer l'anomalie et afficher une erreur.
- **FR-008**: Le système DOIT résoudre la localisation à partir du code `05BAT06V` (valeur fixe renvoyée par le MPI) vers la `Location` openIMIS correspondante, puis fournir son identifiant de base de données à la création : `Family.location_id` et `Insuree.current_village_id`. Le code seul n'est pas un identifiant accepté par l'API GraphQL. Si aucune `Location` active ne porte ce code, la création DOIT être refusée, sans localisation par défaut.
- **FR-009**: La création DOIT porter `audit_user_id` = `id_for_audit` de l'utilisateur technique, avec repli sur la valeur par défaut `-1`. C'est la convention déjà utilisée ailleurs dans openIMIS (`TechnicalUser.id_for_audit` vaut -1 ; `contract`, `payment` et `claim` passent `audit_user_id=-1`). La création NE DOIT PAS exiger la permission de création d'un assuré.
- **FR-010**: La création DOIT être refusée si le Patient n'a pas de nom, de prénoms, de sexe ou de date de naissance. Aucune valeur par défaut ne doit être appliquée.
- **FR-011**: Le système DOIT être idempotent : un CHFID déjà présent (actif) renvoie la fiche existante, sans nouvelle création.
- **FR-012**: En cas d'échec technique (timeout, 5xx, réponse FHIR invalide), le système DOIT afficher une erreur explicite distincte de « CHFID introuvable » et NE DOIT rien créer.
- **FR-013**: Le système NE DOIT journaliser aucune donnée personnelle ; seule une corrélation technique est autorisée.
- **FR-014**: Le comportement de l'enquête locale et le mécanisme existant de création de Family NE DOIVENT PAS être modifiés.

### Key Entities

- **Insuree** : assuré openIMIS identifié par `chf_id` (le CHFID est l'identifiant MPI). Champs d'identité requis : nom, prénoms, sexe, date de naissance. Rattachement à une Family et à une localisation.
- **Family** : famille créée pour l'assuré importé ; il en est le chef (`head_insuree`) et le seul membre. Localisation résolue sur la `Location` de code `05BAT06V`.
- **Patient FHIR (CHC)** : ressource renvoyée par le MPI, porteuse du CHFID et des données d'identité. Un seul Patient attendu par recherche.
- **Transaction openHIM** : trace de l'appel de recherche, utilisée pour l'exploitation et l'audit.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un agent retrouve et crée, en une seule enquête, un assuré présent au CHC et absent localement.
- **SC-002**: Aucune création en double sur des enquêtes répétées du même CHFID.
- **SC-003**: Aucun appel au CHC lorsqu'un assuré existe localement.
- **SC-004**: En cas de panne du CHC, l'agent voit une erreur explicite en moins de 10 secondes et aucune fiche n'est créée.
- **SC-005**: 100 % des fiches créées par le connecteur sont rattachées à une Family dont l'assuré est le chef et le seul membre, avec une localisation résolue sur la `Location` de code `05BAT06V` (son `id` est utilisé à la création).

## Assumptions

- Le CHC est le MPI de référence ; l'identifiant MPI est conservé tel quel comme CHFID dans openIMIS-CSU.
- Le CHC renvoie un seul Patient par recherche et ne renvoie pas de Group.
- La `Location` de code `05BAT06V` existe et est active dans l'environnement cible ; à défaut, la création est refusée.
- L'utilisateur technique a pour valeur d'audit `-1` (`TechnicalUser.id_for_audit`), valeur par défaut utilisée ailleurs dans openIMIS. `audit_user_id` est un entier, sans clé étrangère.
- L'enquête envoie un CHFID exact : aucune recherche partielle n'est utilisée.
- Le chemin FHIR Patient est configurable via `mpi_patient_path` ; la valeur par défaut est `/api/fhir/Patient`.

## Out of Scope

- Claims, Coverage, chèque santé, DCI.
- Nettoyage et normalisation des CHFID existants (#38191, #38348).
- Modification du mécanisme de création de Family.
- Affichage d'une liste de candidats : impossible par construction avec une recherche exacte.
