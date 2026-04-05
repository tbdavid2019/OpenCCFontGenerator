## ADDED Requirements

### Requirement: Support Hong Kong Traditional standard
The system SHALL support generating a font that converts Simplified Chinese characters to Hong Kong Traditional standard characters via OpenCC's `s2hk` mapping.

#### Scenario: User requests Hong Kong Traditional output
- **WHEN** user selects `s2hk` configuration in CLI or wizard
- **THEN** system maps input characters using the `s2hk` OpenCC sequence

### Requirement: Support Taiwan Traditional standard
The system SHALL support generating a font that converts Simplified Chinese characters to Taiwan Traditional standard characters via OpenCC's `s2tw` mapping.

#### Scenario: User requests Taiwan Traditional output
- **WHEN** user selects `s2tw` configuration in CLI or wizard
- **THEN** system maps input characters using the `s2tw` OpenCC sequence
