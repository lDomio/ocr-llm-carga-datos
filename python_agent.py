import json
import io
import PyPDF2
import pytesseract
import os
from typing import Union
from fastapi import FastAPI, UploadFile, File, HTTPException
from typing import Union
from fastapi import FastAPI, UploadFile, File, HTTPException
from PIL import Image
from pydantic import BaseModel, Field
# from google.genai.errors import APIError
# from google import genai
from langchain_google_genai import ChatGoogleGenerativeAI

app = FastAPI()
api_key = os.environ.get("GEMINI_API_KEY")

if not api_key: 
    raise ValueError("La variable de entorno GEMINI_API_KEY no está configurada.")


class InformacionExtraer(BaseModel):
    tipoDocumento: str
    contenidoDocumento: str

class DocumentoExtraido(BaseModel):
    # Campos que se extraen en ambos o se usan como identificador
    tipo_documento: str = Field(default="", alias="tipo") # <-- CORRECCIÓN 1: Sincronizar con 'tipo' del prompt
    monto_total: float = Field(default=0.0)
    fecha: str = Field(default="")
    razon_social: str = Field(default="")
    
    # Campos comunes/Factura
    tipo_de_factura: str = Field(default="")
    producto_servicio: str = Field(default="")
    cuit: str = Field(default="")
    cae: str = Field(default="")
    punto_de_venta_nro: str = Field(default="")
    comprobante_nro: str = Field(default="")
    condicion_frente_al_iva: str = Field(default="")

@app.post('/extraerInfo')
def extraer_informacion(body: InformacionExtraer):

    prompt = f"""
        Eres un experto en Contabilidad e Ingeniería de Datos. Tu tarea es analizar el texto plano proporcionado de un documento fiscal y extraer la información clave.

        **Instrucción de Formato:**
        Debes devolver la respuesta ÚNICAMENTE como un objeto JSON válido, sin ningún texto adicional, preámbulo, explicaciones o marcas de formato como ```json.

        **Documento a analizar:** {body.tipoDocumento}
    """

    
    prompt += f"""
        **Campos Requeridos (y Formato de Salida):**
        1.  **tipo** (string): Debe ser obligatoriamente '{body.tipoDocumento}'.
        2.  **monto_total** (float): Monto total pagado (ej. 150.75). Si no se encuentra, usar 0.0.
        3.  **razon_social** (string): El nombre de la empresa emisora. Si no se encuentra, usar una cadena vacía ("").
    """

    match (body.tipoDocumento):
        case 'factura': prompt += f"""
            4.  **fecha** (string): La Fecha de Emisión de la factura. **PRIORIDAD 1:** Busca el valor que sigue a la etiqueta exacta "Fecha de Emisión:". **PRIORIDAD 2:** Si la "Fecha de Emisión" está ausente o corrupta (como en tu OCR), busca la fecha etiquetada como "Fecha de Vto. para el pago:" o la fecha que se repite. El formato debe ser **DD-MM-AAAA**. Si no se encuentra ninguna fecha válida, usar una cadena vacía ("").
            5.  **tipo_de_factura** (string): Tipo de factura (A, B, C). Si no se encuentra, usar una cadena vacía ("").
            6.  **cuit** (string): El CUIT o identificador fiscal del *emisor*. Si no se encuentra, usar una cadena vacía ("").
            7.  **producto_servicio** (string): El producto por el cual se realiza la compra. Si no se encuentra, usar una cadena vacía ("").
            8.  **cae** (string): El Código de Autorización Electrónico. Si no se encuentra, usar una cadena vacía ("").
            9.  **punto_de_venta_nro** (string): El número de Punto de Venta (ej. 00001). Si no se encuentra, usar una cadena vacía ("").
            10. **comprobante_nro** (string): El número de Comprobante (ej. 00000029). Si no se encuentra, usar una cadena vacía ("").
            11. **condicion_frente_al_iva** (string): La condición frente al IVA del facturador. Busca términos como: **Responsable Monotributo**, **Exento**, **Consumidor Final** o **IVA Responsable Inscripto**. Si no se encuentra, usar una cadena vacía ("").
        """
 
        case 'ticket': prompt += f"""
            4.  **fecha** (string): Fecha de emisión en formato **DD-MM-AAAA** (ej. 05-12-2025). Si no se encuentra, usar una cadena vacía ("").
            5.  **tipo_de_factura** (string): Este campo **DEBE** ser siempre el valor fijo: **"-"** (guion).
            6.  **cuit** (string): Este campo **DEBE** ser siempre el valor fijo: **"-"** (guion).
            7.  **producto_servicio** (string): Este campo **DEBE** ser siempre el valor fijo: **"-"** (guion).
            8.  **cae** (string): Este campo **DEBE** ser siempre el valor fijo: **"-"** (guion).
            9.  **punto_de_venta**: El punto de venta concatenado con el "Comp. Nro", el formato debe ser **00001-00000029**. Si no se encuentra, usar una cadena vacía ("").
            10. **condicion_frente_al_iva**: La condición frente al IVA del facturador. Si no se encuentra, usar una cadena vacía ("").
        """

    prompt += f""""---
        **TEXTO DE ENTRADA:**
        {body.contenidoDocumento}
        ---

        Genera el objeto JSON con **TODOS** los campos requeridos y sus valores (incluyendo los fijos):
    """

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", temperature=0.0, max_output_tokens=1024)

    respuesta = llm.invoke(prompt)

    # 2. Limpiar la respuesta (remover ```json y ```)
    #    Usamos .strip() para eliminar espacios en blanco y saltos de línea al inicio/final
    texto_json_sucio = respuesta.content.strip() 

    # 3. Eliminar las marcas de Markdown que rodean al JSON
    if texto_json_sucio.startswith("```json"):
        texto_json_limpio = texto_json_sucio.lstrip("```json").rstrip("```").strip()
    else:
        texto_json_limpio = texto_json_sucio

    try:
        data_extraida = json.loads(texto_json_limpio)
        documento_validado = DocumentoExtraido(**data_extraida)
        
        # Si quieres retornar el modelo validado como diccionario:
        return documento_validado.model_dump_json()
    except json.JSONDecodeError as e:
        print(f"Error de parsing JSON: {e}")
        return {"error": "json_format_fail"}

@app.post('/revisarPdf')
async def revisar_pdf(file: UploadFile = File(...)):
    # esto validara si se trata de un ticket o una factura
    archivo_bytes = await file.read()

    nombre_archivo = file.filename.lower()

    if nombre_archivo.endswith('.pdf'):
        texto_documento = extraer_texto_pdf(archivo_bytes)
    elif nombre_archivo.endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff')):
        texto_documento = extraer_texto_imagen(archivo_bytes)
    else:
        raise HTTPException(status_code=400, detail='Formato de archivo no soportado. Use PDF o imagen (PNG, JPG, etc)')
    
    if not texto_documento:
        raise HTTPException(status_code=400, detail='No se pudo extraer texto del archivo')
    
    resultado_clasificacion = clasificar_documento_con_llm(texto_documento)

    return {
        "status": "success",
        "tipoDocumento": resultado_clasificacion,
        "contenidoDocumento": texto_documento
    }

@app.get('/')
def helath_check():
    return {"message": "El agente está corriendo. Post a /revisarPdf para usarlo."}

def extraer_texto_pdf(archivo_bytes: bytes) -> str:
    """Extrae texto de un PDF."""
    try:
        lector_pdf = PyPDF2.PdfReader(io.BytesIO(archivo_bytes))
        texto_documento = ""
        for page in lector_pdf.pages:
            texto_documento += page.extract_text() or ""
        return texto_documento
    except Exception as e:
        raise HTTPException(status_code=400, detail=f'Error al procesar el PDF: {e}')

def extraer_texto_imagen(archivo_bytes: bytes) -> str:
    try:
        imagen = Image.open(io.BytesIO(archivo_bytes))
        texto_documento = pytesseract.image_to_string(imagen)
        return texto_documento
    except Exception as e:
        raise HTTPException(status_code=400, detail=f'Error al procesar la imagen: {e}')

def clasificar_documento_con_llm(contenido_del_documento: str) -> str:
    """Clasifica el documento usando un LLM."""

    prompt = f"""
        Eres un experto clasificador de documentos fiscales argentinos.
        
        Tu tarea: Clasificar un documento en UNA de estas categorías:
        - 'factura': Documento fiscal oficial (Factura A, Factura B, Factura C)
        - 'ticket': Comprobante de punto de venta, ticket de caja, recibo
        - 'formulario': Cualquier otro documento (nota de débito, remito, etc)
        
        INDICADORES CLAVE POR TIPO:
        
        FACTURA:
        - Contiene "Factura" (A, B o C)
        - Tiene número de CUIT (ej: 30-12345678-9)
        - Menciona "IVA", "Alícuota", "Subtotal"
        - Tiene fecha de emisión estructurada
        - Número de comprobante en formato XXX-XXXXX
        
        TICKET:
        - Dice "Ticket" o "Recibo"
        - Mencionan "Caja", "Terminal", "Punto de Venta"
        - Formato más simple, menos estructurado
        - Puede tener "Nº de operación" o "Número de ticket"
        - Comprobantes de supermercados, comercios
        
        FORMULARIO:
        - No es factura ni ticket
        - Puede ser: nota de débito, remito, comprobante bancario, etc
        
        IMPORTANTE:
        - Si el documento está corrupto o es ilegible, responde: 'desconocido'
        - Responde ÚNICAMENTE con una palabra: factura, ticket, formulario o desconocido
        - No agregues explicaciones, puntuación ni caracteres adicionales
        
        --- TEXTO DEL DOCUMENTO ---
        {contenido_del_documento}
        --- FIN DEL TEXTO ---
        
        CLASIFICACIÓN (solo una palabra):
    """

    try:
        # respuesta = client.models.generate_content(
        #     model='gemini-2.5-flash',
        #     contents=prompt,
        #     config={
        #         "temperature": 0.0, #queremos una respuesta más determinista que creativa
        #         "max_output_tokens": 1024
        #     }
        # )

        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", temperature=0.0, max_output_tokens=1024)

        respuesta = llm.invoke(prompt)

        if respuesta is None or respuesta.text is None:
            print('La API no devolvió contenido')
            return 'desconocido'
        
        print(respuesta)

        clasificacion = respuesta.content.strip().lower()

        if clasificacion in ['factura', 'ticket', 'formulario']:
            return clasificacion
        else: return 'desconocido'
    except APIError as e:
        print(f'Error en la API del LLM {e}')
        return 'error API'