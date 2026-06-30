# Dokumentacja Połączeń Sprzętowych - scAnt (BTT SKR Pico)

Płyta główna **BigTreeTech SKR Pico V1.0** odpowiada za kontrolę wszystkich osi skanera scAnt.
Silniki krokowe to 42HM48-0406 (NEMA 17, 0.9°/step). Prąd roboczy na TMC2209 jest ustawiony wstępnie na 0.4A w Klipperze.

## Przypisanie Osi (Silniki)

| Oś w scAnt | Element Skanera | Złącze na SKR Pico | Adres UART TMC2209 |
| --- | --- | --- | --- |
| **X** | Ramię Kamery | Złącze `XM` | `0` |
| **Y** | Stół Obrotowy | Złącze `YM` | `2` |
| **Z** | Wózek Ostrości (Focus) | Złącze `ZAM` / `ZBM` | `1` |

*Silniki należy podpiąć bezpośrednio do portów XM, YM, ZAM na płycie.*

## Krańcówki (Endstopy)

Domyślnie system skonfigurowany jest do korzystania z funkcji **Sensorless Homing** (wykrywanie zderzeń przez sterowniki TMC2209, bez dodatkowych kabli). Wymaga to założenia zworek na piny DIAG (oznaczone z boku jako `X-DIAG`, `Y-DIAG`, `Z-DIAG` pod złączami silników na płycie).

Jeżeli chcesz skorzystać z fizycznych krańcówek, zdejmij zworki DIAG i podepnij krańcówki pod odpowiednie porty:
| Oś | Port Krańcówki na Płycie | Pin w Klipperze |
| --- | --- | --- |
| X (Ramię) | Złącze `X-STOP` | `gpio4` |
| Y (Stół) | Złącze `Y-STOP` | `gpio3` |
| Z (Focus) | Złącze `Z-STOP` | `gpio25` |

*(Pamiętaj, by w pliku `config/skr_pico_klipper.cfg` zakomentować linię `endstop_pin: tmc2209_stepper...` i odkomentować linię z odpowiednim gpio).*

## Komunikacja

Płytę SKR Pico podłączamy do portu USB w Raspberry Pi dołączonym kablem USB-C. Raspberry Pi zasili elektronikę logiki płyty, a także nawiąże z nią połączenie szeregowe do sterowania (wymagane zaktualizowanie ścieżki `/dev/serial/by-id/...` w pliku cfg).

Silniki wymagają dodatkowego zasilania 12-24V doprowadzonego do gniazda `DC-IN` (terminal blokowy) na płycie SKR Pico.
