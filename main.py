from __future__ import print_function
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from httplib2 import Http
from oauth2client import file, client, tools
from bs4 import BeautifulSoup
import requests
import os

# If modifying these scopes, delete the file token.json.
SCOPES = 'https://www.googleapis.com/auth/drive'
REKO_URL = 'http://reko.utem.cl/aula/'
PAUTAS_UTEM_ID = '1c7Z6kDvuP_H3XotiyQMW8wE76Kwq9LjH'
FOLDER_MIME_TYPE = 'application/vnd.google-apps.folder'
H = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36',
    'Referer': 'http://reko.utem.cl/portal/'
}

def login(rut, contrasenia):
        s = requests.Session()
        url = REKO_URL + 'index.php'
        payload = {'usuario': rut, 'clave': contrasenia, 'enviar': 'true'}
        s.post(url, data=payload, headers=H)
        return s

def get_asignaturas(s):
    r = s.get(REKO_URL + 'asignaturas.php', headers=H)
    soup = BeautifulSoup(r.content, features='html.parser')
    tabla = soup.find('table', attrs={'class':'table_main'})
    filas = tabla.find('tbody').find_all('tr')
    return filas

def get_contenidos(uri, s):
    r = s.get(REKO_URL + uri, headers=H)
    soup = BeautifulSoup(r.content, features='html.parser')
    tabla = soup.find('table', attrs={'class':'table_main'})
    strong = tabla.find('strong')
    if strong is not None and strong.text.startswith("Los Contenidos para este curso"):
        return []
    else:
        filas = tabla.find('tbody').find_all('tr')
        return filas

def get_archivos(uri, s):
    r = s.get(REKO_URL + uri, headers=H)
    soup = BeautifulSoup(r.content, features='html.parser')
    anchors = soup.find('div', attrs={'class':'contenido'}).find_all('a', href=True)
    return anchors

def descargar_archivo(nombre, uri, s):
    print("Descargando " + nombre + " desde Reko...")
    r = s.get(REKO_URL + uri, headers=H, stream=True)
    with open('temp/' + nombre, 'wb') as f:
        f.write(r.content)
    return nombre

def eliminar_archivo(nombre):
    if os.path.exists('temp/' + nombre):
        os.remove('temp/' + nombre)

def subir_archivo(service, nombre, parents):
    print("Subiendo " + nombre + " a Drive...")
    file_metadata = {
            'name': nombre,
            'parents': parents
        }
    media = MediaFileUpload('temp/' + nombre)
    file = service.files().create(body=file_metadata,
                                        media_body=media,
                                        fields='id').execute()
    return file.get('id')

def crear_carpeta(service, nombre, parents):
    file_metadata = {
        'name': nombre,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': parents
    }
    file = service.files().create(body=file_metadata,
                                        fields='id').execute()
    return file.get('id')

def buscar_carpeta(service, nombre, parents):
    q = "mimeType='%s' and name='%s' and '%s' in parents" % (FOLDER_MIME_TYPE, nombre, parents)
    response = service.files().list(q=q,
                                    spaces='drive',
                                    fields='nextPageToken, files(id, name)').execute()
    for file in response.get('files', []):
        return file.get('id')
    return None

def buscar_archivo(service, nombre, parents):
    q = "name='%s' and '%s' in parents" % (nombre, parents)
    response = service.files().list(q=q,
                                    spaces='drive',
                                    fields='nextPageToken, files(id, name)').execute()
    for file in response.get('files', []):
        return file.get('id')
    return None

def main():
    store = file.Storage('token.json')
    creds = store.get()
    if not creds or creds.invalid:
        print("Error obteniendo un token valido.")
        """flow = client.flow_from_clientsecrets('credentials.json', SCOPES)
        creds = tools.run_flow(flow, store)"""
    else:
        service = build('drive', 'v3', http=creds.authorize(Http()))
        s = login(19649846, '19649846k')
        asignaturas = get_asignaturas(s)
        for asignatura in asignaturas:
            a = asignatura.find('a', href=True)
            nombre = a.text
            href = a['href']
            codigo = href.replace('asignaturas.php?cualasig=', '').replace('&show=t', '')
            carpeta = codigo + ' - ' + nombre
            id_asignatura = buscar_carpeta(service, carpeta, PAUTAS_UTEM_ID)
            if id_asignatura is None:
                id_asignatura = crear_carpeta(service, carpeta, [PAUTAS_UTEM_ID])
            contenidos = get_contenidos(href, s)
            if contenidos:
                for contenido in contenidos:
                    a = contenido.find('a', href=True)
                    nombre = a.text
                    href = a['href']
                    carpeta = href.split('llaveid=')[-1] + ' - ' + nombre
                    id_contenido = buscar_carpeta(service, carpeta, id_asignatura)
                    if id_contenido is None:
                        id_contenido = crear_carpeta(service, carpeta, [id_asignatura])
                    
                    archivos = get_archivos(href, s)
                    for archivo in archivos:
                        href = archivo['href']
                        if href.startswith("download.php?"):
                            nombre = href.split('filename=')[-1]
                            if buscar_archivo(service, nombre, id_contenido) is None:
                                descargar_archivo(nombre, href, s)
                                subir_archivo(service, nombre, [id_contenido])
                                eliminar_archivo(nombre)

if __name__ == '__main__':
    main()