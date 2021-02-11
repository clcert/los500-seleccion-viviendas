import csv
import clcert_chachagen
import json
import requests
import io
import argparse
import hmac
import hashlib
import datetime


def esc(code):
    return f'\033[{code}m'


def format_date(s):
    date = datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S.000Z')
    return date.strftime('%d/%m/%Y %H:%M:%S UTC')


parser = argparse.ArgumentParser(description='Lxs 400 - Selección aleatoria de Índices de Viviendas (Selección Extendida).')
parser.add_argument('-s', dest='secret', action="store", default="", type=str,
                    help="Valor aleatorio (en hexadecimal) secreto que será combinado con el pulso aleatorio público. (Por defecto sín secreto)")
parser.add_argument('-f', dest='date', action="store", default="", type=str,
                    help="Fecha (formato Epoch con milisegundos) del pulso aleatorio público que será utilizado. (Por defecto último pulso generado)")
parser.add_argument('-n', dest='files', action="store", default=1, type=int,
                    help="Número de archivos a generar con los resultados de las viviendas seleccionadas. (Por defecto 1)")
args = parser.parse_args()

print('[Lxs 400] Selección Aleatoria de Índices de Viviendas\n')

print('🏠 Seleccionando índices de viviendas 🏠')

## 1° Obtener semilla aleatoria desde Random UChile

print('(1/5) Obteniendo pulso aleatorio desde Random UChile... ', end='', flush=True)

if args.date == "":
    pulse_url = "https://random.uchile.cl/beacon/2.0/pulse/last"
else:
    pulse_url = "https://random.uchile.cl/beacon/2.0/pulse/time/" + args.date

print(esc('32') + 'ok' u'\u2713' + esc(0))

## 2° Construir semilla aleatorio combinando secreto y pulso (HMAC), y crear PRNG con dicha semilla aleatoria

print('(2/5) Construyendo semilla aleatoria y PRNG combinando pulso con secreto... ', end='', flush=True)

pulse = json.loads(requests.get(pulse_url).content)["pulse"]
pulse_date = format_date(pulse["timeStamp"])
pulse_index = str(pulse["chainIndex"]) + '-' + str(pulse["pulseIndex"])
pulse_uri = str(pulse["uri"])
pulse_value = pulse["outputValue"]
seed = hmac.HMAC(bytes.fromhex(args.secret), bytes.fromhex(pulse_value), hashlib.sha3_512).hexdigest()
chacha_prng = clcert_chachagen.ChaChaGen(seed)

print(esc('32') + 'ok' u'\u2713' + esc(0))

## 3° Revisar cuantas veces fue seleccionada cada manzana y escoger índices de viviendas a escoger

print('(3/5) Seleccionando aleatoriamente los índices de las viviendas en cada manzana... ', end='', flush=True)

# Leer primer archivo con 30.000 manzanas, para recordar índices ya escogidos
input_filename = "resultados_manzanas_detalle_30000.csv"
viviendas_seleccionadas = {}
with open(input_filename, 'rt') as input_file:
    reader = csv.DictReader(io.StringIO(input_file.read()))
    for row in reader:
        total = row['TOTAL_VIVIENDAS']
        times = row['TIMES_SELECTED']
        selected_indexes = chacha_prng.sample(range(1, int(total) + 1), int(times))
        viviendas_seleccionadas[row['MANZENT']] = selected_indexes

# Leer segundo archivo con 15.000 manzanas y guardar solamente nuevos índices escogidos (selección extendida)
input_filename_2 = "resultados_manzanas_detalle_last15000.csv"
viviendas_seleccionadas_2 = []
with open(input_filename_2, 'rt') as input_file:
    reader = csv.DictReader(io.StringIO(input_file.read()))
    for row in reader:
        total = row['TOTAL_VIVIENDAS']
        times = row['TIMES_SELECTED']
        try:
            while(True):
                selected_indexes = chacha_prng.sample(range(1, int(total) + 1), int(times))
                # Revisar si índice de vivienda ya fue escogido anteriormente
                if not any(item in viviendas_seleccionadas[row['MANZENT']] for item in selected_indexes):
                    break
        except KeyError:
            pass
        viviendas_seleccionadas_2.append({'MANZENT': row['MANZENT'],
                                          'REGION': row['REGION'],
                                          'COMUNA': row['COMUNA'],
                                          'INDICES_VIVIENDAS': selected_indexes})

print(esc('32') + 'ok' u'\u2713' + esc(0))

## 4° Revolver el orden de las viviendas seleccionadas (selección extendida)

print('(4/5) Revolviendo viviendas seleccionadas...', end='', flush=True)

indices_viviendas = []
counter = 0
for vivienda in viviendas_seleccionadas_2:
    for index in sorted(vivienda['INDICES_VIVIENDAS']):
        counter += 1
        indices_viviendas.append({'MANZENT': vivienda['MANZENT'],
                                  'REGION': vivienda['REGION'],
                                  'COMUNA': vivienda['COMUNA'],
                                  'INDICE_VIVIENDA': index})
indices_viviendas_shuffled = chacha_prng.shuffle(indices_viviendas)

print(esc('32') + 'ok' u'\u2713' + esc(0))

## 5° Generar archivos de salida con los índices de las viviendas seleccionadas (selección extendida)

print('(5/5) Generando archivos con los resultados...', end='', flush=True)

out_columns = ['MANZENT', 'REGION', 'COMUNA', 'INDICE_VIVIENDA']
for i in range(args.files):
    output_filename = "resultados_indices_viviendas_" + str(i) + ".csv"
    with open(output_filename, 'w') as out_file:
        writer = csv.DictWriter(out_file, fieldnames=out_columns)
        writer.writeheader()
        init = int(i * counter / args.files)
        end = int((i + 1) * counter / args.files)
        for vivienda in indices_viviendas_shuffled[init:end]:
            writer.writerow({'MANZENT': vivienda['MANZENT'],
                             'REGION': vivienda['REGION'],
                             'COMUNA': vivienda['COMUNA'],
                             'INDICE_VIVIENDA': vivienda['INDICE_VIVIENDA']})

print(esc('32') + 'ok' u'\u2713' + esc(0))

print('🏠 ¡Selección realizada con éxito! 🏠')

print('\nResumen de la Selección')
print('‣ Fecha pulso aleatorio: ' + pulse_date + ' (' + pulse_uri + ')')
print('‣ Número de viviendas seleccionadas: ' + str(counter))
print('‣ Número de archivos generados: ' + str(args.files))

print('\n🎲 Random UChile 🎲')
print('Entra a https://random.uchile.cl/lxs400 para mayor información')
