## Purpose
Fix incorrect character mapping for "面" in the Taiwan Phrases (twp) configuration.

## Requirements

## ADDED Requirements

### Requirement: Support Taiwan Traditional with Phrases (twp)
The system SHALL support generating a font that converts Simplified Chinese characters to Taiwan Traditional standard characters including common phrases via the `twp` mapping.

#### Scenario: User requests Taiwan Traditional with Phrases output
- **WHEN** user selects `twp` configuration in CLI or wizard
- **THEN** system maps input characters using the `twp` OpenCC sequence, which includes both single-character and multi-character phrase substitutions.

### Requirement: Conservative mapping for ambiguous characters in twp
The system SHALL use conservative mappings for ambiguous characters in the `twp` character table where a single Simplified character can map to multiple Traditional meanings. Specifically, "面" (U+9762) MUST remain "面" at the character level to preserve its "face/surface/side" meanings.

#### Scenario: Substituted '面' character mapping
- **WHEN** generating a font with the `twp` configuration
- **THEN** the character "面" maps to "面" in the single-character translation table
- **AND** phrase-level mapping (e.g., "麵條") still correctly uses the "麵" character
