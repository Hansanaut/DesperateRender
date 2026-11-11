# Desperate Render™ — Arbeitsanleitung für KI-generierte Experimente

**Zweck:** Diese Anleitung beschreibt den Arbeitsablauf für eine KI, die neue Desperate Render™-Experimente entwerfen, als JSON erzeugen und für den Import vorbereiten soll.

**Verbindliche Referenz:** Für exakte Felder, Enums, Matrixoperatoren, Seed-Regeln und JSON-Beispiele ist `DESPERATE_RENDER_AI_EXPERIMENT_JSON_GUIDE_REV2.md` maßgeblich. Bei Abweichungen hat der aktuelle Quellcode Vorrang. Diese Datei ergänzt die Referenz um den praktischen Ablauf und Qualitätsregeln.

## 1. Ziel vor dem JSON klären

Formuliere zuerst die Frage, die das Experiment beantworten soll. Beispiele:

- Welcher Prompt erzeugt die klarste Silhouette?
- Wie wirken drei Guidance-Scale-Werte auf dasselbe Motiv?
- Welche Kombination aus Prompt-Variante und Auflösung funktioniert am besten?

Definiere anschließend:

- **Zielgröße:** Was soll visuell verglichen oder bewertet werden?
- **Variablen:** Welche Einstellungen dürfen sich ändern?
- **Konstanten:** Welche Einstellungen müssen identisch bleiben?
- **Umfang:** Wie viele Konfigurationen beziehungsweise Bilder sind sinnvoll?
- **Erfolgskriterium:** Woran wird entschieden, welche Variante besser ist?

Eine Matrix sollte eine konkrete Frage untersuchen. Verändere nicht gleichzeitig viele unabhängige Parameter, wenn dadurch die Ursache eines Ergebnisses unklar wird.

## 2. Baseline festlegen

Lege eine reproduzierbare Baseline fest, bevor du Varianten hinzufügst. Halte alle nicht untersuchten Parameter konstant, insbesondere:

- Base Model und gegebenenfalls Refiner
- Auflösung und Aspect Ratio
- Seed-Modus und Seed-Werte
- Guidance Scale und Sharpness
- Styles und LoRAs
- positive und negative Prompt-Bestandteile
- Referenzbilder und deren Rolle

Wenn ein Parameter selbst untersucht werden soll, definiere seine konkreten Testwerte ausdrücklich. Erfinde keine Modellnamen, Style-Namen oder Dateipfade. Verwende nur Werte, die in den Projektdateien, der installierten Umgebung oder vom Nutzer bereitgestellten Angaben belegt sind.

## 3. Prompt-Dimensionen entwerfen

Nutze `prompt_blocks` für unabhängige positive Prompt-Dimensionen. Gib jedem Block eine eindeutige Buchstaben-ID und einen aussagekräftigen Namen. Jeder Prompt-Slot benötigt eine eindeutige `slot_id` innerhalb seines Blocks, den vollständigen Prompttext und den `fixed`-Status.

- Ein **variabler Prompt** nimmt an der Auswahl gemäß `matrix_selection` teil.
- Ein **fixed Prompt** bleibt Bestandteil jeder Variante dieses Blocks.
- Der Text jedes Prompt-Slots muss für sich verständlich und vollständig sein, soweit die gewünschte Matrixlogik dies verlangt.
- Verwende keine Platzhalter wie `A1`, `B2` oder `PROMPT_3` als Prompttext. Solche IDs dienen nur der internen Herkunfts- und Variantenzuordnung; sie ersetzen niemals den eigentlichen Prompt.
- Negative Prompts sollen bewusst konstant oder als eigene untersuchte Dimension geplant werden. Erzeuge keine unbeabsichtigten Duplikate.

Bei älteren Dateien mit `positive_prompts` beachte die Legacy-Regeln in der JSON-Referenz. Vermische Legacy-Felder und Prompt Blocks nicht willkürlich.

## 4. Matrixoperatoren bewusst auswählen

Leite die Bedeutung der Operatoren aus der aktuellen `matrix_builder.py` und der JSON-Referenz ab. Wähle den Operator anhand des Versuchsdesigns, nicht anhand einer Vermutung.

- Nutze eine Auswahl einzelner Alternativen, wenn jeweils eine Prompt-Alternative getestet werden soll.
- Nutze Permutationen nur dann, wenn Reihenfolge und Anordnung der ausgewählten Elemente tatsächlich untersucht werden sollen.
- Nutze Kombinationen nur dann, wenn mehrere Elemente gemeinsam ausgewählt werden sollen.
- Aktiviere numerische Matrizen für Guidance Scale, Sharpness oder Auflösung nur mit gültigen Grenzen und Schrittangaben.
- Prüfe, ob mehrere Dimensionen ein kartesisches Produkt bilden und dadurch die Anzahl der Konfigurationen multiplizieren.

Bevor du JSON ausgibst, berechne die erwartete Anzahl der Konfigurationen anhand der tatsächlichen Builder-Regeln. Wenn die Zahl groß wird, weise darauf hin und biete eine kleinere Matrix an, statt stillschweigend Dimensionen zu entfernen.

## 5. JSON erzeugen

Erzeuge ein vollständiges UTF-8-JSON-Objekt mit allen erforderlichen Feldern und passenden Datentypen. Nutze die aktuelle Datei `DESPERATE_RENDER_AI_EXPERIMENT_JSON_GUIDE_REV2.md` für:

- Pflichtfelder und Metadaten
- gültige Status- und Seed-Werte
- PromptSlot- und PromptBlock-Strukturen
- `generation`-Einstellungen
- `matrix`-Auswahl und numerische Matrizen
- Styles und Referenzbilder
- vollständige Beispielstruktur

Setze `experiment_id`, `created_at` und `updated_at` konsistent. Verwende ISO-8601-Datetime-Strings. Behaupte nicht, dass Referenzbilder in JSON eingebettet sind: Referenzen benötigen tatsächlich vorhandene Dateien und korrekte Pfade.

## 6. Validieren, nicht nur plausibilisieren

Führe diese Prüfungen durch:

1. JSON syntaktisch parsen.
2. Pflichtfelder, Datentypen und Enum-Werte prüfen.
3. Prompt-Block-IDs und Slot-IDs auf Gültigkeit und Eindeutigkeit prüfen.
4. Prüfen, dass jeder Prompt Block eine gültige `matrix_selection` besitzt.
5. Numerische Werte und Min/Max/Schritte gegen die Implementierung prüfen.
6. Seed-Modus und Seed-Werte auf Konsistenz prüfen.
7. Referenzbilder und Style-Namen nur dann als gültig markieren, wenn sie verifiziert wurden.
8. Erwartete Konfigurationszahl unabhängig nachrechnen.
9. Wenn möglich, die Datei mit `ExperimentStore` laden und die Konfigurationen mit `MatrixBuilder` aufbauen.
10. Bei Fehlern die Ursache beheben und erneut validieren; Fehler nicht durch Weglassen unbekannter Felder kaschieren.

Eine syntaktisch gültige JSON-Datei gilt nicht automatisch als importierbares oder korrekt ausführbares Experiment.

## 7. Reproduzierbarkeit und Dateiausgabe

Gib gemeinsam mit der JSON-Datei eine kurze Zusammenfassung aus:

- Forschungsfrage und Baseline
- untersuchte Dimensionen und Konstanten
- verwendete Matrixoperatoren
- erwartete Konfigurationszahl und deren Berechnung
- benötigte externe Referenzdateien
- validierte Aspekte und noch nicht verifizierte Annahmen

Überschreibe oder lösche keine existierenden Experimentdefinitionen oder Revisionen. Experimentdefinitionen, Result-History und tatsächlich generierte Bilder sind unterschiedliche Dinge; eine neu erzeugte Experimentdefinition enthält nicht automatisch generierte Ergebnisse.

## 8. Regeln, die niemals verletzt werden dürfen

- Prompt-IDs sind keine Prompt-Inhalte.
- Keine erfundenen Pfade, Referenzbilder, Styles oder Modellnamen.
- Keine unbestätigten Parameterbereiche als Fakten darstellen.
- Nicht mehrere Variablen ändern, wenn das Experiment deren Einfluss getrennt bestimmen soll.
- Die Anzahl der Varianten nicht schätzen, wenn sie aus der Matrixlogik berechnet werden kann.
- Keine bestehende Experimenthistorie überschreiben oder löschen.
- Unsicherheiten klar markieren und die Datei nach Möglichkeit mit dem echten Store und Builder testen.

## 9. Arbeitsauftrag an die KI

Entwirf zunächst einen nachvollziehbaren Versuchsplan. Erzeuge danach die JSON-Datei anhand der aktuellen Referenz und des aktuellen Codes, berechne die erwartete Konfigurationszahl und validiere die Struktur. Liefere die JSON-Datei mit einer kurzen, verständlichen Erklärung der Versuchslogik und kennzeichne jede Annahme, die nicht verifiziert werden konnte.
