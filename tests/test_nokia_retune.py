"""Nokia_Retune: frequency parsing, ITU grid validation, sequences."""
import pytest

from Nokia_Retune import (parse_frequency, validate_on_grid, retune_sequence,
                          ITU_GRID_GHZ, ghz_to_nm)


@pytest.mark.parametrize('text', ['193.3', '193300', '193300000',
                                  'ch33', 'c33', '33'])
def test_all_input_forms_resolve_to_same_mhz(text):
    mhz, err = parse_frequency(text)
    assert err is None
    assert mhz == 193300000


def test_grid_matches_fiberdyne_reference():
    # spot values straight from the Fiberdyne ITU C-band 100 GHz PDF
    assert validate_on_grid(190100000)['channel'] == 1
    assert validate_on_grid(190100000)['wavelength_nm'] == 1577.03
    assert validate_on_grid(193300000)['channel'] == 33
    assert validate_on_grid(193300000)['wavelength_nm'] == 1550.92
    assert validate_on_grid(197200000)['channel'] == 72
    assert validate_on_grid(197200000)['wavelength_nm'] == 1520.25
    assert len(ITU_GRID_GHZ) == 72


def test_grid_units_consistent():
    g = validate_on_grid(195500000)     # the 195500000 in Tuning Commands.txt
    assert g['freq_thz'] == 195.5
    assert g['freq_ghz'] == 195500
    assert abs(ghz_to_nm(195500) - g['wavelength_nm']) < 0.01


@pytest.mark.parametrize('mhz', [
    193350000,   # 50 GHz offset - not on 100 GHz grid
    189900000,   # below band
    197300000,   # above band
    193300500,   # not a whole GHz
])
def test_off_grid_refused(mhz):
    assert validate_on_grid(mhz) is None


@pytest.mark.parametrize('text', ['199.5', 'ch73', 'ch0', 'garbage', '42.5'])
def test_bad_input_rejected(text):
    mhz, err = parse_frequency(text)
    assert err is not None or validate_on_grid(mhz) is None


def test_sequence_matches_tuning_commands_txt():
    assert retune_sequence('1/1/17', 193300000) == [
        'configure exclusive',
        'port 1/1/17',
        'dwdm frequency 193300000',
        'validate',
        'compare',
        'commit',
        'quit-config',
    ]
