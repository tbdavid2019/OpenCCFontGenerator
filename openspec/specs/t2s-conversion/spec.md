## ADDED Requirements

### Requirement: Traditional to Simplified conversion support
The system SHALL support creating a font that converts from Traditional Chinese to Simplified Chinese, functioning conversely to the standard `s2t` mode.

#### Scenario: User selects T2S generation
- **WHEN** user provides a Traditional Chinese font and selects `t2s` mode
- **THEN** system generates a font using `t2s` mapping to display Simplified characters instead of Traditional ones
