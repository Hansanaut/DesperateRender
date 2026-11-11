# Desperate Render™ – KI-Referenz für Experiment-SAVE-Dateien (Revision 2)

**Revision:** 2  
**Zweck:** Verbindliche Referenz für eine KI, die Desperate-Render-Experimente entwirft, als JSON definiert, validiert und für den Import vorbereitet.  
**Status:** Gegen den Repository-Stand auf Branch `main` geprüft.

Dies ist die deutsche Fassung der englischen Referenz `DESPERATE_RENDER_AI_EXPERIMENT_JSON_GUIDE_REV2_EN.md`. Beide Sprachfassungen sollen inhaltlich gleichwertig bleiben. Wenn Dokumentation und Anwendungsverhalten voneinander abweichen, hat der aktuelle Quellcode Vorrang.

---

## 1. Zweck und wichtige Abgrenzungen

Eine Experiment-SAVE-Datei beschreibt **die Definition eines Experiments**. Sie ist weder eine Liste bereits eingereihter Jobs noch ein Ergebnismanifest, eine Sammlung generierter Bilder oder eine Garantie dafür, dass Fooocus jede Einstellung zur Laufzeit akzeptiert.

Die KI muss eine verständliche Experimentdefinition erstellen und anhand der Builder-Logik die erwartete Anzahl konkreter Generierungskonfigurationen bestimmen. Gültige JSON-Syntax allein reicht nicht aus.

Zentrale Implementierungsdateien:

- `models/experiment.py` – Datenmodelle, Enums, Standardwerte und Größenkonstanten.
- `models/prompt_block.py` – Modell der Prompt Blocks und Ermittlung ihrer Variantenkennungen.
- `models/generation_configuration.py` – Konfiguration eines einzelnen Generierungsjobs.
- `services/experiment/experiment_store.py` – JSON-Serialisierung, Deserialisierung, Speicherung und Referenzpfade.
- `services/experiment/matrix_builder.py` – Matrixexpansion und Erzeugung der Konfigurationen.

Ergänzende Tests und Prüfstellen sind unter anderem:

- `tools/test_experiment_store.py` – Save/Load und Referenzbilder.
- `tools/test_experiment_store_numeric_roundtrip.py` – numerische Matrixparameter.

## 2. SAVE-Dateien, Speicherung und Revisionen

### 2.1 Format

- UTF-8-kodiertes JSON.
- **Zwingende Vorgabe: Der Dateiname muss exakt auf `_exp.json` enden.** Der LOAD-Befehl verwendet dieses Suffix, um Experiment-SAVE-Dateien zu finden. Dateien, die lediglich auf `.json` enden und den Bestandteil `_exp` nicht enthalten, werden über die normale LOAD-Dateisuche nicht direkt gefunden.
- Dies ist eine funktionale Voraussetzung und nicht nur eine bevorzugte Namenskonvention des Stores.
- Die Anwendung speichert Experimentdefinitionen in datumsbezogenen Unterverzeichnissen.

### 2.2 Tatsächliche Namenskonvention

Das Experimentverzeichnis hat folgendes Format:

```text
<Experiment-Root>/<bereinigter-Experimentname>_YYYYMMDD/
```

Der JSON-Dateiname muss diesem Muster folgen und in jedem Fall das exakte Suffix `_exp.json` behalten:

```text
YYYYMMDD-HHMMSS-<bereinigter-Experimentname>_exp.json
```

**Eine Experiment-SAVE-Datei darf nicht in eine Datei mit einfachem `.json`-Suffix umbenannt oder mit einem solchen Suffix erzeugt werden. Der LOAD-Befehl findet sie bei seiner normalen Dateisuche nicht.**

Falls der Dateiname bereits existiert, wird ein Suffix ergänzt, zum Beispiel `...-2_exp.json`. Der Zeitstempel basiert auf `updated_at`. Der Store aktualisiert diesen Wert unmittelbar vor jedem expliziten Speichern.

### 2.3 Verhalten bei Revisionen

- Jedes explizite Speichern erzeugt eine neue JSON-Revision.
- Frühere JSON-Revisionen werden vom Store weder überschrieben noch gelöscht.
- `created_at` bleibt unverändert; `updated_at` ändert sich bei jedem Speichern.
- Die logische `experiment_id` bleibt über alle Revisionen desselben Experiments hinweg gleich.
- Der Store erzeugt neue logische IDs üblicherweise im Format `YYYYMMDD-NNN`, zum Beispiel `20261101-001`. Diese ID ist nicht mit dem JSON-Dateinamen identisch.
- Das Löschen oder Überschreiben vorhandener Revisionen gehört nicht zu den Aufgaben einer KI.

### 2.4 Referenzbilder

Beim Speichern werden Referenzbilder in ein revisionsspezifisches Verzeichnis kopiert. Das JSON speichert relative Pfade innerhalb dieser Revision; der Loader löst diese beim Laden zu absoluten Pfaden auf. Referenzbilder sind nicht in das JSON eingebettet. Die Dateien müssen separat vorhanden und für den Store erreichbar sein.

## 3. Struktur der obersten JSON-Ebene

Das oberste JSON-Objekt entspricht dem Modell `Experiment`.

| Feld | Typ | Bedeutung |
|---|---|---|
| `experiment_id` | String | Erforderliche logische Experiment-ID |
| `name` | String | Anzeigename |
| `version` | Integer | Versionsnummer der Definition; Standard `1` |
| `status` | Enum-String | Status des Experiments |
| `created_at` | ISO-Datetime | Erforderlicher Erstellungszeitpunkt |
| `updated_at` | ISO-Datetime | Erforderlicher Änderungszeitpunkt |
| `positive_prompts` | Array | Legacy-Slots für positive Prompts |
| `negative_prompts` | Array | Negative Prompt-Slots |
| `prompt_blocks` | Array | Unabhängige positive Prompt-Dimensionen |
| `styles` | String-Array | Tatsächlich ausgewählte Styles |
| `available_styles` | String-Array | Gespeicherter Style-Pool; wird vom MatrixBuilder nicht zur Auswahl verwendet |
| `random_style` | Boolean | Zufällige Style-Auswahl aktivieren |
| `random_style_count` | Integer | Anzahl zufällig ausgewählter Styles |
| `style_references` | Array | Stil-Referenzbilder |
| `composition_references` | Array | Kompositions-Referenzbilder |
| `generation` | Objekt | Feste Generierungseinstellungen und Seed-Verhalten |
| `matrix` | Objekt | Auswahlregeln der Experimentdimensionen |
| `configuration_count` | Integer | Vom Builder ermittelte Konfigurationsanzahl |
| `total_image_count` | Integer | Abgeleiteter Zähler, derzeit an `configuration_count` gekoppelt |
| `estimated_runtime_seconds` | Zahl oder `null` | Laufzeitschätzung |
| `estimated_storage_bytes` | Integer oder `null` | Speicherplatzschätzung |
| `test_run_completed` | Boolean | Kennzeichnet einen abgeschlossenen Testlauf |

### 3.1 Statuswerte

Unterstützte Werte:

- `DRAFT`
- `READY`
- `RUNNING`
- `PAUSED`
- `ABORTED`
- `FAILED`
- `COMPLETED`

Für ein neu entworfenes Experiment ist `DRAFT` zu verwenden.

### 3.2 Pflichtfelder und Loader-Standardwerte

Der Loader verlangt `experiment_id`, `created_at` und `updated_at`. Diese Felder müssen immer enthalten sein. Andere Felder können Modell- oder Loader-Standardwerte erhalten; eine vollständige SAVE-Datei sollte jedoch alle zentralen Felder ausdrücklich enthalten.

Zeitstempel müssen mit `datetime.fromisoformat()` lesbar sein, zum Beispiel `2026-11-01T12:00:00`. Der Status wird gegen das Enum geprüft; ein unbekannter Wert führt zu einem Ladefehler.

`experiment_id` ist eine logische ID und nicht der Dateiname. Der Store erzeugt IDs üblicherweise im Datumsformat, zum Beispiel `20261101-001`.

## 4. Prompt-Daten

### 4.1 PromptSlot

Positive und negative Prompts verwenden das Modell `PromptSlot`:

| Feld | Typ | Regel |
|---|---|---|
| `slot_id` | Integer | Erforderlich; innerhalb der jeweiligen Liste oder des Blocks eindeutig |
| `text` | String | Prompttext; Standard ist leer |
| `fixed` | Boolean | Fester Bestandteil; Standard `false` |

Beispiel:

```json
{"slot_id": 1, "text": "a glass Erlenmeyer flask", "fixed": false}
```

`fixed: true` bedeutet, dass der Prompt keine variable Matrixalternative ist und in jeder Variante erhalten bleibt. Slot-IDs müssen innerhalb derselben Liste beziehungsweise desselben Blocks eindeutig sein. Verschiedene Blocks dürfen dieselben Slot-IDs verwenden.

### 4.2 Legacy-Feld `positive_prompts`

- Wenn kein nichtleerer Prompt Block existiert, kann der Builder die Legacy-Dimension verwenden.
- Sobald mindestens ein Prompt Block Inhalt enthält, ersetzt der Prompt-Block-Modus die Legacy-Dimension für positive Prompts.
- Neue Experimente sollten positive Prompts nicht gleichzeitig über Legacy-Slots und Prompt Blocks steuern.
- Der Prompt-Block-Editor kann vorhandene Legacy-Prompts in den initialen Block A übertragen. Bereits gespeicherte Prompt Blocks bleiben maßgeblich.
- Bei Legacy-Prompts bleiben feste Slots in jeder Variante erhalten; nur nicht feste Slots werden variiert.

Zusätzliche Migrationsregel für ältere Experimente: Beim Öffnen des Prompt-Block-Editors können vorhandene, nichtleere `positive_prompts` in den initialen Block A übernommen werden. Prompttext und `fixed`-Status bleiben erhalten. Bereits gespeicherte Prompt Blocks dürfen nicht durch Legacy-Inhalte überschrieben werden. Ein leerer Platzhalter-Block darf vorhandene Legacy-Prompts nicht verdrängen.

### 4.3 `negative_prompts`

Negative Prompts sind ebenfalls `PromptSlot`-Objekte. Ist die Liste nicht leer, wird sie als Matrixdimension verarbeitet. Feste negative Prompts bleiben in jeder Variante erhalten.

### 4.4 `prompt_blocks`

Beispiel:

```json
{
  "block_id": "A",
  "name": "Motiv",
  "prompts": [
    {"slot_id": 1, "text": "a glass Erlenmeyer flask", "fixed": false},
    {"slot_id": 2, "text": "a futuristic glass Erlenmeyer flask", "fixed": false}
  ],
  "matrix_selection": {"operator": "INDIVIDUAL", "minimum": null, "maximum": null}
}
```

Regeln:

- `block_id` muss genau ein alphabetisches Zeichen sein; der Wert wird getrimmt und in Großbuchstaben umgewandelt.
- `name` ist der lesbare Name der Dimension.
- `prompts` enthält die `PromptSlot`-Objekte des Blocks.
- `matrix_selection` steuert die Auswahl der variablen Prompts.
- Leere Blocks werden ignoriert.
- Ein Block, der ausschließlich feste Prompts enthält, erzeugt eine Variante, in der diese Prompts erhalten bleiben.
- Die Reihenfolge der Blocks und Prompts ist relevant.
- Alle nichtleeren Blocks werden als kartesisches Produkt kombiniert. Die ausgewählten Prompttexte werden in Block-Reihenfolge zusammengesetzt.
- Varianten-IDs kombinieren Block- und Slot-IDs, zum Beispiel `A2+B1`. Die aktuelle Methode `PromptBlock.variant_id()` berücksichtigt auch feste Prompts in der Kennung; feste Prompts bleiben außerdem im endgültigen Prompt enthalten.

Typische unabhängige Dimensionen sind Block A Motiv, Block B Beleuchtung, Block C Perspektive und Block D Hintergrund.

## 5. `generation` – feste Generierungseinstellungen

Aktuelle Standardwerte von `GenerationSettings`:

| Feld | Typ | Standard | Bedeutung |
|---|---|---:|---|
| `width` | Integer | 1024 | Basisbreite |
| `height` | Integer | 768 | Basishöhe |
| `aspect_ratio` | String | `"4:3"` | Gespeichertes Seitenverhältnis |
| `seed_mode` | Enum-String | `"RANDOM"` | `FIXED` oder `RANDOM` |
| `seed` | Integer oder `null` | `null` | Legacy-Einzel-Seed |
| `seeds` | Integer-Array | `[]` | Manuelle Seed-Liste |
| `random_seed_count` | Integer | 1 | Anzahl Seeds pro Matrixkombination |
| `random_seed_fixed` | Boolean | `true` | Zufalls-Seeds einmal erzeugen und wiederverwenden |
| `random_seeds` | Integer-Array | `[]` | Gespeicherte Seeds im Fixed-Random-Modus |
| `performance` | String oder `null` | `null` | Fooocus-Performanceeinstellung |
| `guidance_scale` | Zahl oder `null` | `null` | Fester Basiswert für Guidance Scale |
| `sharpness` | Zahl oder `null` | `null` | Fester Basiswert für Sharpness |
| `base_model` | String oder `null` | `null` | Legacy-/Einzelmodell |
| `base_models` | String-Array | `[]` | Mehrere Basismodelle |
| `refiner_model` | String oder `null` | `null` | Ein Refiner-Modell |
| `refiner_switch` | Zahl oder `null` | `null` | Refiner-Switch-Wert |
| `output_format` | String | `"png"` | Ausgabeformat |

Wichtig: Der Modellstandard für `seed_mode` ist `RANDOM`, nicht `FIXED`. Für reproduzierbare Beispiele mit festen Seeds muss `FIXED` ausdrücklich gesetzt werden.

### 5.1 Seed-Verhalten im MatrixBuilder

**`FIXED`**

- Wenn `seeds` nicht leer ist, wird jeder Eintrag als eigene äußere Seed-Variante verwendet.
- Andernfalls wird `seed` als einzelner Seed verwendet.
- Sind beide leer beziehungsweise `null`, kann eine Konfiguration einen `null`-Seed enthalten. Für reproduzierbare Experimente müssen konkrete Seeds angegeben werden.

**`RANDOM` mit `random_seed_fixed = true`**

- Der Builder erzeugt die mit `random_seed_count` angeforderte Anzahl Seeds.
- Vorhandene `random_seeds` werden wiederverwendet; fehlende Seeds werden erzeugt.
- Die Seeds werden am Experiment gespeichert und über die Matrixkombinationen hinweg wiederverwendet.
- Sie bilden eine äußere Dimension und vervielfachen die Konfigurationsanzahl.

**`RANDOM` mit `random_seed_fixed = false`**

- Es wird keine feste Seed-Dimension im Voraus expandiert.
- Jeder konkrete Job erhält einen neu erzeugten Seed.
- `random_seed_count` Jobs beziehungsweise Seeds werden für jede Kombination und gegebenenfalls für jeden zufällig ausgewählten Style erzeugt.
- Diese Seeds werden nicht als wiederverwendbare Dimension vorab gespeichert.

Der Builder behandelt `random_seed_count` mindestens als `1`. Für reproduzierbare Vergleiche `FIXED` mit expliziten Seeds oder `RANDOM` mit gespeicherten Fixed-Random-Seeds verwenden. `RANDOM` mit `random_seed_fixed = false` ist für unabhängige Zufalls-Seeds pro Job gedacht.

Legacy-Kompatibilität: Wenn `seeds` leer und `seed` gesetzt ist, überträgt der Loader den Legacy-Wert in die Seed-Liste.

### 5.2 Basismodelle und Refiner

- Wenn `generation.base_models` Einträge enthält, verwendet der Builder diese Liste als Basismodell-Dimension.
- Andernfalls wird ein gesetztes `generation.base_model` als einzelne Legacy-Alternative verwendet.
- Die Auswahlregel dafür ist `matrix.base_models`.
- Das aktuelle Modell `GenerationSettings` besitzt nur einen String `refiner_model`.
- Der Builder verarbeitet ihn als Ein-Element-Liste. `matrix.refiner_models` existiert, kann derzeit aber nicht zwischen mehreren Refiner-Modellen auswählen.

Es darf nicht angenommen werden, dass mehrere Refiner-Modelle unterstützt werden.

## 6. `matrix` – Auswahlregeln und Kombinatorik

### 6.1 MatrixSelection

Diskrete Dimensionen verwenden:

```json
{"operator": "INDIVIDUAL", "minimum": null, "maximum": null}
```

Unterstützte Operatoren:

- `INDIVIDUAL` – jeder Wert wird zu einer eigenen Variante.
- `ALL` – alle Werte werden zu einer gemeinsamen Variante zusammengefasst.
- `PERMUTATION` – geordnete Gruppen.
- `COMBINATION` – ungeordnete Gruppen.

Für `PERMUTATION` und `COMBINATION` muss `minimum` mindestens `1` sein. `maximum` muss mindestens `minimum` und darf nicht größer als die Anzahl der Werte sein. Fehlende Grenzen werden standardmäßig als `1` beziehungsweise als Anzahl der Werte behandelt.

### 6.2 Diskrete Matrixdimensionen

Für die Werte A, B und C ergibt sich:

| Operator | Einstellung | Varianten |
|---|---|---:|
| `INDIVIDUAL` | – | 3 |
| `ALL` | – | 1 |
| `PERMUTATION` | min 1, max 3 | 15 |
| `PERMUTATION` | min 2, max 2 | 6 |
| `COMBINATION` | min 1, max 3 | 7 |
| `COMBINATION` | min 2, max 2 | 3 |

Bei einer leeren Werteliste liefert `MatrixBuilder.build()` eine leere Auswahl `()`. Diese wirkt als neutrale Dimension im kartesischen Produkt. Eine leere Dimension bedeutet also nicht automatisch null Konfigurationen.

Die Datenmodellfelder für `MatrixSelection` sind:

- `positive_prompts`
- `negative_prompts`
- `styles`
- `seeds`
- `style_references`
- `composition_references`
- `base_models`
- `refiner_models`
- `lora_configurations`

Der aktuelle `iter_experiment()` verarbeitet tatsächlich folgende Dimensionen: Legacy-Positive-Prompts (sofern nicht der Prompt-Block-Modus mit nichtleeren Blocks aktiv ist), negative Prompts, Styles bei deaktiviertem Random Style, Style-Referenzen, Kompositions-Referenzen, Basismodelle, ein konfiguriertes Refiner-Modell, Guidance Scale, Sharpness und Resolution.

Seeds und Prompt Blocks werden separat über eigene Schleifen beziehungsweise Produktexpansionen behandelt.

**LoRA:** `lora_configurations` ist im Matrixmodell vorhanden, wird vom aktuellen `iter_experiment()` aber nicht als Dimension verarbeitet. Aus der Existenz des Feldes darf keine aktive LoRA-Experimentunterstützung abgeleitet werden.

### 6.3 Numerische MatrixSelection: Guidance Scale und Sharpness

Guidance Scale und Sharpness verwenden `NumericMatrixSelection`, nicht `MatrixSelection`:

```json
{"enabled": true, "minimum": 2.0, "maximum": 8.0, "steps": 4}
```

| Feld | Typ | Bedeutung |
|---|---|---|
| `enabled` | Boolean | Aktiviert oder deaktiviert die Dimension |
| `minimum` | Zahl oder `null` | Unterer Wert |
| `maximum` | Zahl oder `null` | Oberer Wert |
| `steps` | Integer | Anzahl der erzeugten Werte, nicht Anzahl der Intervalle |

Regeln des Builders:

- Wenn deaktiviert, werden keine Werte erzeugt.
- Wenn aktiviert, müssen `minimum` und `maximum` gesetzt sein.
- `steps` muss mindestens `1` sein.
- `maximum` darf nicht kleiner als `minimum` sein.
- Bei `steps = 1` wird nur `minimum` ausgegeben.
- Bei `steps > 1` muss `maximum > minimum` gelten.
- Mehrere Werte werden gleichmäßig einschließlich beider Grenzen verteilt.
- Die Werte werden auf zehn Dezimalstellen gerundet.

Beispiel: `minimum = 2`, `maximum = 8`, `steps = 4` ergibt `[2.0, 4.0, 6.0, 8.0]`.

Die Werte bilden eine `INDIVIDUAL`-Dimension und überschreiben den entsprechenden Basiswert in `generation.guidance_scale` beziehungsweise `generation.sharpness`. Die von Fooocus akzeptierten Wertebereiche müssen separat anhand der installierten Konfiguration und Laufzeit geprüft werden.

### 6.4 ResolutionMatrixSelection

Die Auflösung verwendet eine eigene Struktur:

```json
{"enabled": true, "dimension": "width", "minimum": 600, "maximum": 1200, "steps": 3}
```

| Feld | Typ | Bedeutung |
|---|---|---|
| `enabled` | Boolean | Aktiviert oder deaktiviert die Auflösungsmatrix |
| `dimension` | String | `"width"` oder `"height"` |
| `minimum` | Integer oder `null` | Untere Grenze der variierten Achse |
| `maximum` | Integer oder `null` | Obere Grenze der variierten Achse |
| `steps` | Integer | Anzahl gleichmäßig verteilter Werte einschließlich der Grenzen |

Aktuelle Regeln des Builders:

- `dimension` muss exakt `width` oder `height` sein.
- Fehlende Werte für `minimum` und `maximum` werden auf den aktuellen Basiswert der ausgewählten Achse gesetzt.
- `steps` muss mindestens `1` sein; `maximum` darf nicht kleiner als `minimum` sein.
- Die ausgewählte Achse muss innerhalb der Modellgrenzen liegen: Breite 480–2048 Pixel, Höhe 320–2048 Pixel.
- Die andere Achse wird aus dem Verhältnis `generation.width / generation.height` abgeleitet, auf ganze Pixel gerundet und muss ebenfalls innerhalb ihrer Modellgrenzen liegen.
- Bei `steps = 1` wird nur `minimum` ausgegeben.
- Die erzeugten Maße werden direkt der `GenerationConfiguration` zugewiesen; es findet keine spätere Bildskalierung statt.

Beispiel: Bei einer Basis von 1024 × 768 und einer Breite von 600 bis 1200 mit drei Schritten entstehen:

```text
600 × 450
900 × 675
1200 × 900
```

**Wichtig – 8-Pixel-Ausrichtung:** Das Modell definiert `GENERATION_SIZE_STEP = 8`, der `MatrixBuilder` erzwingt diese Schrittweite jedoch nicht. Er prüft die Grenzen und das abgeleitete Seitenverhältnis, nicht die Teilbarkeit durch 8. Für Fooocus-kompatible Experimente müssen Breite und Höhe – einschließlich der abgeleiteten Dimension – durch 8 teilbar sein. Jede resultierende Auflösung ist ausdrücklich zu prüfen.

**Seitenverhältnis:** Breite und Höhe werden aus dem Verhältnis der Basiswerte abgeleitet. `generation.aspect_ratio` wird dabei nicht neu berechnet, sondern unverändert an `GenerationConfiguration` übergeben. Der Wert muss daher zu den Basismaßen passen.

### 6.5 Kartesisches Produkt und tatsächliche Konfigurationsanzahl

Aktive Dimensionen werden grundsätzlich als kartesisches Produkt kombiniert. Beispiel: 3 Varianten × 4 Varianten × 2 Prompt-Block-Varianten × 2 feste Seeds ergeben 48 Konfigurationen, sofern keine Sonderregeln eingreifen.

Die Anzahl darf nicht einfach durch Multiplikation der Arraylängen berechnet werden. Zu berücksichtigen sind Matrixoperatoren, feste und variable `PromptSlot`-Objekte, Prompt-Block-Produkte, Seed-Modus und `random_seed_count`, Random-Style-Verhalten sowie ausschließlich die Dimensionen, die der Builder tatsächlich aktiviert und verarbeitet.

Die zuverlässigste Prüfung ist ein Aufruf von `MatrixBuilder.build_experiment()` und das Zählen der zurückgegebenen Konfigurationen. Alternativ kann `iter_experiment()` vollständig durchlaufen werden. Eine vollständige Iteration aktualisiert `configuration_count` und darüber auch `total_image_count`. Ein nur teilweise konsumierter Generator liefert keine endgültige Anzahl.

## 7. Styles und Random Style

Beispiel:

```json
{
  "styles": ["Fooocus V2", "Fooocus Enhance"],
  "available_styles": ["Fooocus V2", "Fooocus Enhance"],
  "random_style": false,
  "random_style_count": 1
}
```

- `styles` enthält die tatsächlich ausgewählten Styles.
- `available_styles` dokumentiert den verfügbaren Fooocus-Style-Pool.
- `random_style` aktiviert die zufällige Auswahl aus `styles`.
- `random_style_count` gibt die Anzahl der pro Basiskombination ausgewählten Styles an.

Aktuelles Builder-Verhalten:

- Bei `random_style = false` werden Styles über `matrix.styles` als reguläre Dimension verarbeitet.
- Bei `random_style = true` entfällt die reguläre Style-Dimension. Der Builder wählt stattdessen für jede Basiskombination zufällig aus `styles` aus.
- Jeder ausgewählte Style erzeugt eine eigene `GenerationConfiguration`.
- `random_style_count` wird effektiv mindestens als `1` behandelt.
- Random Style mit einer leeren `styles`-Liste schlägt fehl.
- Ein `random_style_count`, das größer als die Anzahl der ausgewählten Styles ist, schlägt fehl.

`available_styles` wird vom `MatrixBuilder` nicht zur Auswahl verwendet. Die tatsächliche Auswahlliste ist `styles`. Es dürfen keine Style-Namen erfunden werden; zu verwenden sind nur Namen, die im installierten Style-Pool bestätigt wurden.

Random Style garantiert bei erneuter Ausführung nicht dieselbe Auswahl. Für reproduzierbare Style-Vergleiche ist die reguläre Style-Matrix mit expliziten Auswahlen zu verwenden.

## 8. Referenzbilder

`style_references` und `composition_references` enthalten Objekte wie:

```json
{
  "reference_id": 1,
  "path": "Experiment/style/001_reference.png",
  "reference_type": "STYLE"
}
```

| Feld | Typ | Regel |
|---|---|---|
| `reference_id` | Integer | Erforderliche Referenz-ID |
| `path` | String | Pfad zur tatsächlichen Bilddatei |
| `reference_type` | Enum-String | `STYLE` oder `COMPOSITION` |

Der Typ muss zur jeweiligen Liste passen: `style_references` → `STYLE`; `composition_references` → `COMPOSITION`.

Regeln:

1. Referenzpfade niemals erfinden.
2. Vor dem Import prüfen, dass jede referenzierte Datei existiert.
3. Wenn keine Referenzen vorhanden sind, leere Arrays verwenden.
4. Bei extern erzeugtem JSON müssen relative Pfade zum geplanten Experimentverzeichnis passen; alternativ können erreichbare absolute Pfade angegeben werden.
5. Beim Speichern kopiert der Store die Dateien in die Revision und schreibt relative Pfade in das gespeicherte JSON.
6. Frühere Revisionsverzeichnisse und deren Referenzdaten niemals verändern oder entfernen.

## 9. Vollständiges Schema-Beispiel

Dieses Beispiel verwendet Prompt Blocks, zwei feste Seeds und eine numerische Guidance-Scale-Matrix. Es enthält keine Referenzbilder und keine unbestätigten Style-Namen.

```json
{
  "experiment_id": "20261101-001",
  "name": "Cyberpunk Erlenmeyer",
  "version": 1,
  "status": "DRAFT",
  "created_at": "2026-11-01T12:00:00",
  "updated_at": "2026-11-01T12:00:00",
  "positive_prompts": [],
  "negative_prompts": [
    {"slot_id": 1, "text": "blurry, low quality, distorted geometry", "fixed": true}
  ],
  "prompt_blocks": [
    {
      "block_id": "A",
      "name": "Motiv",
      "prompts": [
        {"slot_id": 1, "text": "a glass Erlenmeyer flask", "fixed": false},
        {"slot_id": 2, "text": "a futuristic glass Erlenmeyer flask", "fixed": false}
      ],
      "matrix_selection": {"operator": "INDIVIDUAL", "minimum": null, "maximum": null}
    },
    {
      "block_id": "B",
      "name": "Beleuchtung",
      "prompts": [
        {"slot_id": 1, "text": "cyan and magenta neon lighting", "fixed": false},
        {"slot_id": 2, "text": "dramatic volumetric lighting", "fixed": false}
      ],
      "matrix_selection": {"operator": "INDIVIDUAL", "minimum": null, "maximum": null}
    }
  ],
  "styles": [],
  "available_styles": [],
  "random_style": false,
  "random_style_count": 1,
  "style_references": [],
  "composition_references": [],
  "generation": {
    "width": 1024,
    "height": 768,
    "aspect_ratio": "4:3",
    "seed_mode": "FIXED",
    "seed": 12345,
    "seeds": [12345, 23456],
    "random_seed_count": 1,
    "random_seed_fixed": true,
    "random_seeds": [],
    "performance": null,
    "guidance_scale": null,
    "sharpness": null,
    "base_model": null,
    "base_models": [],
    "refiner_model": null,
    "refiner_switch": null,
    "output_format": "png"
  },
  "matrix": {
    "positive_prompts": {"operator": "INDIVIDUAL", "minimum": null, "maximum": null},
    "negative_prompts": {"operator": "INDIVIDUAL", "minimum": null, "maximum": null},
    "styles": {"operator": "INDIVIDUAL", "minimum": null, "maximum": null},
    "seeds": {"operator": "INDIVIDUAL", "minimum": null, "maximum": null},
    "style_references": {"operator": "INDIVIDUAL", "minimum": null, "maximum": null},
    "composition_references": {"operator": "INDIVIDUAL", "minimum": null, "maximum": null},
    "base_models": {"operator": "INDIVIDUAL", "minimum": null, "maximum": null},
    "refiner_models": {"operator": "INDIVIDUAL", "minimum": null, "maximum": null},
    "lora_configurations": {"operator": "INDIVIDUAL", "minimum": null, "maximum": null},
    "guidance_scale": {"enabled": true, "minimum": 2.0, "maximum": 8.0, "steps": 4},
    "sharpness": {"enabled": false, "minimum": null, "maximum": null, "steps": 1},
    "resolution": {"enabled": false, "dimension": "width", "minimum": null, "maximum": null, "steps": 3}
  },
  "configuration_count": 0,
  "total_image_count": 0,
  "estimated_runtime_seconds": null,
  "estimated_storage_bytes": null,
  "test_run_completed": false
}
```

### 9.1 Erwartete Konfigurationsanzahl

- Block A: 2 Varianten.
- Block B: 2 Varianten.
- Prompt-Block-Produkt: 2 × 2 = 4 Varianten.
- Guidance Scale: 4 Werte (2.0, 4.0, 6.0, 8.0).
- Feste Seeds: 2.
- Negativer Prompt: fest, erzeugt daher keine zusätzliche multiplikative Dimension.

Erwartetes Ergebnis: **4 × 4 × 2 = 32 `GenerationConfiguration`-Objekte.**

Die Zähler stehen absichtlich auf `0`. Es handelt sich um abgeleitete Werte, die durch einen vollständig ausgeführten Builder aktualisiert werden. Sie belegen nicht, dass bereits Bilder generiert wurden.

## 10. KI-Arbeitsablauf zum Erstellen eines Experiments

1. **Forschungsfrage klären:** Was soll verglichen oder untersucht werden? Hypothese und untersuchten Faktor bestimmen.
2. **Baseline definieren:** Alle nicht untersuchten Parameter konstant halten.
3. **Dimensionen auswählen:** Nur tatsächlich benötigte Dimensionen aktivieren.
4. **Prompt-Struktur wählen:** Für neue unabhängige positive Prompt-Dimensionen Prompt Blocks verwenden. Legacy-Positive-Prompts nur aus Gründen der Rückwärtskompatibilität nutzen.
5. **Werte und Operatoren festlegen:** Matrixoperatoren passend zur beabsichtigten Vergleichslogik wählen.
6. **Seeds definieren:** Explizite Seeds oder den Fixed-Random-Modus für reproduzierbare Vergleiche verwenden.
7. **JSON anhand des aktuellen Modells erstellen:** Korrekte Feldnamen, Typen, Enum-Werte und Pflichtzeitstempel verwenden.
8. **Konfigurationsanzahl ermitteln:** Aktive Dimensionen, Prompt Blocks, Seeds und Random-Style-Regeln berücksichtigen.
9. **Validieren:** JSON-Syntax, Store-Laden, Builder-Ausführung, Referenzdateien, Style-Namen und Fooocus-Parameter prüfen.
10. **Ausliefern:** JSON, kurze Beschreibung der Experimentlogik, Baseline, variierte Faktoren und erwartete Konfigurationsanzahl bereitstellen.

## 11. Validierungscheckliste

Vor der Ausgabe einer Experimentdatei:

- [ ] Gültiges UTF-8-JSON.
- [ ] **Dateiname endet exakt auf `_exp.json` (zwingend für die LOAD-Dateisuche).**
- [ ] `experiment_id`, `created_at` und `updated_at` sind vorhanden.
- [ ] Zeitstempel sind mit `datetime.fromisoformat()` lesbar.
- [ ] Statuswert ist gültig.
- [ ] `PromptSlot`-Objekte besitzen gültige `slot_id`-Werte sowie korrekt typisierte Felder `text` und `fixed`.
- [ ] Prompt-Block-IDs bestehen aus genau einem alphabetischen Zeichen.
- [ ] Jeder Prompt Block besitzt eine gültige `matrix_selection`.
- [ ] Slot-IDs sind innerhalb derselben Liste beziehungsweise desselben Blocks eindeutig.
- [ ] Legacy-Positive-Prompts und Prompt Blocks werden nicht unbeabsichtigt gleichzeitig verwendet.
- [ ] Alle Operatoren sind gültig.
- [ ] Grenzen für `PERMUTATION` und `COMBINATION` sind zulässig.
- [ ] Aktivierte numerische Dimensionen besitzen `minimum`, `maximum` und eine gültige Schrittanzahl.
- [ ] Bei `NumericMatrixSelection` mit `steps > 1` gilt `maximum > minimum`.
- [ ] Eine aktivierte Auflösungsmatrix besitzt gültige Achse, Grenzen und Schrittanzahl.
- [ ] Alle abgeleiteten Auflösungen liegen innerhalb der Modellgrenzen.
- [ ] Breite und Höhe sind für Fooocus durch 8 teilbar.
- [ ] `generation.aspect_ratio` passt zu den Basismaßen.
- [ ] Seeds und Seed-Modus entsprechen dem Experimentplan.
- [ ] Gespeicherte Seeds werden nach dem Aufbau von RANDOM-Experimenten mit `random_seed_fixed = true` berücksichtigt.
- [ ] Random Style verwendet ausschließlich bestätigte Namen aus `styles`.
- [ ] Referenzbilder sind tatsächlich vorhanden.
- [ ] Annahmen zu Refiner und Basismodellen entsprechen den unterstützten Feldern.
- [ ] LoRA wird nicht als aktive Matrixdimension vorausgesetzt.
- [ ] Die erwartete Konfigurationsanzahl wurde mit dem aktuellen `MatrixBuilder` überprüft.
- [ ] `configuration_count` und `total_image_count` werden nicht mit bereits erzeugten Bildern verwechselt.
- [ ] Vorhandene Revisionen und Referenzverzeichnisse werden weder überschrieben noch gelöscht.

## 12. Nicht ungeprüft annehmen

Folgende Punkte müssen anhand der installierten Fooocus-Version, der aktuellen Laufzeit oder einer tatsächlichen Anwendungsausführung geprüft werden:

- Akzeptierte Wertebereiche für Guidance Scale, Sharpness und Refiner Switch.
- Ob ein Style-Name in der installierten Fooocus-Version existiert.
- Ob ein Basis- oder Refiner-Modell installiert und verwendbar ist.
- Ob Referenzpfade auf dem Zielsystem existieren und für die Anwendung lesbar sind.
- Ob zusätzliche Parameter vom Fooocus-Bridge-Code tatsächlich an die Generierung übergeben werden.
- Ob die erzeugten Bildmaße von der konkreten Fooocus-Version akzeptiert werden.
- Ob das Experiment nicht nur geladen, sondern auch erfolgreich ausgeführt werden kann.

Die Existenz eines Feldes im JSON-Modell beweist nicht, dass jede nachgelagerte Komponente es unterstützt.

## 13. Abschließende Arbeitsanweisung an die KI

Erzeuge gültige, verständliche und reproduzierbare Desperate-Render-Experimente. Verwende ausschließlich dokumentierte Felder und gültige Werte. Leite Matrix-, Prompt-Block-, Seed- und Random-Style-Verhalten aus der tatsächlichen Implementierung ab.

Erfinde keine Referenzdateien, Style-Namen, Modellnamen oder Parametergrenzen. Unterscheide immer zwischen:

- der gespeicherten Experimentdefinition,
- den vom `MatrixBuilder` erzeugten `GenerationConfiguration`-Objekten,
- tatsächlich eingereihten oder ausgeführten Jobs,
- tatsächlich erzeugten Bildern und Ergebnisdaten.

Berechne die erwartete Konfigurationsanzahl und überprüfe sie, soweit möglich, durch Laden des Experiments mit dem aktuellen `ExperimentStore` und vollständigen Aufbau mit dem aktuellen `MatrixBuilder`. Annahmen, die sich nicht anhand von Code oder Laufzeit prüfen ließen, müssen klar gekennzeichnet werden.

**Qualitätsziel:** Die Experimentdatei muss sich in der aktuellen Version von Desperate Render laden lassen und exakt die beabsichtigten Generierungskonfigurationen erzeugen. Syntaktisch gültiges JSON, das nicht durch Store und Builder geprüft wurde, ist noch kein verifiziertes Experiment.
