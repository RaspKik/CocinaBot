# -*- coding: utf-8 -*-
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler,
    CallbackQueryHandler
)
import json
import os
import logging
import datetime

# --- CONFIGURACIÓN ---
TOKEN = '7728529418:AAE6OGBgvtUA0IUyoBCUdnbQNTvnQ7FMZH4'
INVENTARIO_FILE = 'inventario.json'
REGISTRO_FILE = 'registro.log'
ALLOWED_USER_IDS = {222105389}

# --- ESTADOS DE CONVERSACIÓN ---
(
    ESPERANDO_PRODUCTO_ANADIR, ESPERANDO_CANTIDAD_ANADIR, ESPERANDO_MINIMO_ANADIR, UBICACION_ANADIR,
    ESPERANDO_PRODUCTO_SACAR, ESPERANDO_CANTIDAD_SACAR, UBICACION_SACAR, ESPERANDO_SELECCION_PRODUCTO,
    ESPERANDO_PRODUCTO_BUSCAR, ESPERANDO_UBICACION_ORIGEN, ESPERANDO_UBICACION_DESTINO, ESPERANDO_CANTIDAD_TRASPASO
) = range(12)

# --- CONFIGURACIÓN DE LOGGING ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- FUNCIONES DE INVENTARIO ---
def cargar_inventario():
    if os.path.exists(INVENTARIO_FILE):
        try:
            with open(INVENTARIO_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for ubicacion in data.values():
                    for item in ubicacion:
                        if 'minimo' not in item:
                            item['minimo'] = 0
                return data
        except Exception as e:
            logger.error(f"Error cargando inventario: {e}")
            return {
                "nevera": [], "congelador": [], "despensa": [],
                "baño": [], "trastero": []
            }
    return {
        "nevera": [], "congelador": [], "despensa": [],
        "baño": [], "trastero": []
    }

def guardar_inventario(inventario):
    try:
        if os.path.exists(INVENTARIO_FILE):
            import shutil
            shutil.copyfile(INVENTARIO_FILE, INVENTARIO_FILE + '.bak')
        
        with open(INVENTARIO_FILE, 'w', encoding='utf-8') as f:
            json.dump(inventario, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Error guardando inventario: {e}")

def generar_lista_compra(inventario):
    lista_compra = []
    for ubicacion, productos in inventario.items():
        for item in productos:
            if item['minimo'] > 0 and item['cantidad'] <= item['minimo']:
                lista_compra.append({
                    'nombre': item['nombre'],
                    'necesario': item['minimo'] - item['cantidad'] + 1,
                    'ubicacion': ubicacion
                })
    return lista_compra

def registrar_accion(user_id: int, accion: str, producto: str, cantidad: int, ubicacion: str = None, detalles: str = ""):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(REGISTRO_FILE, 'a', encoding='utf-8') as f:
        ubicacion_info = f" | {ubicacion}" if ubicacion else ""
        detalles_info = f" | {detalles}" if detalles else ""
        f.write(f"{timestamp} | User {user_id} | {accion.upper()} {cantidad}x {producto}{ubicacion_info}{detalles_info}\n")

# --- FUNCIONES PARA MOSTRAR INVENTARIO ---
async def mostrar_inventario(update: Update, ubicacion=None):
    inventario = cargar_inventario()
    emoji_map = {
        'nevera': '❄️ Nevera', 'congelador': '🧊 Congelador',
        'despensa': '🥫 Despensa', 'baño': '🚿 Baño',
        'trastero': '📦 Trastero'
    }
    
    if ubicacion:
        if ubicacion in inventario:
            mensaje = f"{emoji_map.get(ubicacion, ubicacion.capitalize())}:\n"
            for item in inventario[ubicacion]:
                alerta = " ⚠️" if item['minimo'] > 0 and item['cantidad'] <= item['minimo'] else ""
                mensaje += f"- {item['nombre'].capitalize()} ({item['cantidad']}/{item['minimo']}){alerta}\n"
        else:
            mensaje = f"Ubicación '{ubicacion}' no encontrada"
    else:
        mensaje = "📦 Inventario Completo:\n\n"
        for zona, productos in inventario.items():
            mensaje += f"{emoji_map.get(zona, zona.capitalize())}:\n"
            for item in productos:
                alerta = " ⚠️" if item['minimo'] > 0 and item['cantidad'] <= item['minimo'] else ""
                mensaje += f"- {item['nombre'].capitalize()} ({item['cantidad']}/{item['minimo']}){alerta}\n"
            mensaje += "\n"
    
    if hasattr(update, 'callback_query'):
        await update.callback_query.message.reply_text(mensaje)
    else:
        await update.message.reply_text(mensaje)

async def mostrar_lista_compra(update: Update):
    inventario = cargar_inventario()
    lista = generar_lista_compra(inventario)
    
    if not lista:
        mensaje = "✅ No hay productos por comprar (todo está por encima del mínimo)"
    else:
        productos_unicos = list({item['nombre'] for item in lista})
        mensaje = "🛒 Lista de la compra:\n\n" + "\n".join(f"- {producto.capitalize()}" for producto in productos_unicos)
    
    if hasattr(update, 'callback_query'):
        await update.callback_query.message.reply_text(mensaje)
    else:
        await update.message.reply_text(mensaje)

async def mostrar_menu_inventario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📦 Completo", callback_data='ver_completo')],
        [InlineKeyboardButton("❄️ Nevera", callback_data='ver_nevera')],
        [InlineKeyboardButton("🧊 Congelador", callback_data='ver_congelador')],
        [InlineKeyboardButton("🥫 Despensa", callback_data='ver_despensa')],
        [InlineKeyboardButton("🚿 Baño", callback_data='ver_baño')],
        [InlineKeyboardButton("📦 Trastero", callback_data='ver_trastero')],
        [InlineKeyboardButton("🛒 Lista compra", callback_data='lista_compra')],
        [InlineKeyboardButton("⬅️ Volver", callback_data='menu_principal')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text('Selecciona una opción:', reply_markup=reply_markup)

# --- FUNCIONES PARA TRASPASAR PRODUCTOS ---
async def iniciar_traspaso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("❄️ Nevera", callback_data='traspaso_origen_nevera')],
        [InlineKeyboardButton("🧊 Congelador", callback_data='traspaso_origen_congelador')],
        [InlineKeyboardButton("🥫 Despensa", callback_data='traspaso_origen_despensa')],
        [InlineKeyboardButton("🚿 Baño", callback_data='traspaso_origen_baño')],
        [InlineKeyboardButton("📦 Trastero", callback_data='traspaso_origen_trastero')],
        [InlineKeyboardButton("❌ Cancelar", callback_data='cancelar_traspaso')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text('Selecciona la ubicación de ORIGEN:', reply_markup=reply_markup)
    return ESPERANDO_UBICACION_ORIGEN

async def seleccionar_origen_traspaso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    origen = query.data.split('_')[2]
    context.user_data['origen_traspaso'] = origen
    
    keyboard = [
        [InlineKeyboardButton("❄️ Nevera", callback_data='traspaso_destino_nevera')],
        [InlineKeyboardButton("🧊 Congelador", callback_data='traspaso_destino_congelador')],
        [InlineKeyboardButton("🥫 Despensa", callback_data='traspaso_destino_despensa')],
        [InlineKeyboardButton("🚿 Baño", callback_data='traspaso_destino_baño')],
        [InlineKeyboardButton("📦 Trastero", callback_data='traspaso_destino_trastero')],
        [InlineKeyboardButton("❌ Cancelar", callback_data='cancelar_traspaso')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text('Selecciona la ubicación de DESTINO:', reply_markup=reply_markup)
    return ESPERANDO_UBICACION_DESTINO

async def seleccionar_destino_traspaso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    destino = query.data.split('_')[2]
    origen = context.user_data['origen_traspaso']
    
    if origen == destino:
        await query.message.reply_text('⚠️ No puedes traspasar a la misma ubicación')
        return ConversationHandler.END
    
    context.user_data['destino_traspaso'] = destino
    inventario = cargar_inventario()
    
    if not inventario[origen]:
        await query.message.reply_text(f'⚠️ La ubicación {origen} está vacía')
        return ConversationHandler.END
    
    keyboard = []
    for item in inventario[origen]:
        keyboard.append([InlineKeyboardButton(
            f"{item['nombre'].capitalize()} ({item['cantidad']} u.)",
            callback_data=f"seleccionar_traspaso_{item['nombre'].replace(' ', '_')}"
        )])
    
    keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data='cancelar_traspaso')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text('Selecciona el producto a traspasar:', reply_markup=reply_markup)
    return ESPERANDO_PRODUCTO_SACAR

async def seleccionar_producto_traspaso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    producto = query.data.split('_')[2].replace('_', ' ')
    context.user_data['producto_traspaso'] = producto
    
    origen = context.user_data['origen_traspaso']
    inventario = cargar_inventario()
    
    for item in inventario[origen]:
        if item['nombre'] == producto:
            context.user_data['max_cantidad_traspaso'] = item['cantidad']
            await query.message.reply_text(
                f'¿Cuántas unidades de {producto.capitalize()} quieres traspasar? '
                f'(Máximo: {item["cantidad"]})'
            )
            return ESPERANDO_CANTIDAD_TRASPASO
    
    await query.message.reply_text('⚠️ Producto no encontrado')
    return ConversationHandler.END

async def confirmar_traspaso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        cantidad = int(update.message.text)
        origen = context.user_data['origen_traspaso']
        destino = context.user_data['destino_traspaso']
        producto = context.user_data['producto_traspaso']
        max_cantidad = context.user_data['max_cantidad_traspaso']
        
        if cantidad <= 0 or cantidad > max_cantidad:
            raise ValueError
        
        inventario = cargar_inventario()
        item_origen = None
        item_destino = None
        
        # Buscar en origen
        for item in inventario[origen]:
            if item['nombre'] == producto:
                item_origen = item
                break
        
        if not item_origen:
            await update.message.reply_text('⚠️ Producto no encontrado en origen')
            return ConversationHandler.END
        
        # Verificar cantidad
        if item_origen['cantidad'] < cantidad:
            await update.message.reply_text('⚠️ No hay suficientes unidades')
            return ConversationHandler.END
        
        # Buscar en destino
        for item in inventario[destino]:
            if item['nombre'] == producto:
                item_destino = item
                break
        
        # Actualizar cantidades
        item_origen['cantidad'] -= cantidad
        
        if item_destino:
            item_destino['cantidad'] += cantidad
        else:
            inventario[destino].append({
                'nombre': producto,
                'cantidad': cantidad,
                'minimo': 0
            })
        
        guardar_inventario(inventario)
        
        registrar_accion(
            user_id=update.effective_user.id,
            accion="TRASPASO",
            producto=producto,
            cantidad=cantidad,
            ubicacion=origen,
            detalles=f"de {origen} a {destino}"
        )
        
        # Verificar mínimo en origen
        if item_origen['minimo'] > 0 and item_origen['cantidad'] <= item_origen['minimo']:
            await update.message.reply_text(
                f'✅ Traspasadas {cantidad} unidades de {producto.capitalize()} de {origen} a {destino}\n'
                f'⚠️ Atención: {producto.capitalize()} en {origen} ha alcanzado el mínimo ({item_origen["minimo"]})'
            )
        else:
            await update.message.reply_text(
                f'✅ Traspasadas {cantidad} unidades de {producto.capitalize()} de {origen} a {destino}'
            )
        
        return ConversationHandler.END
    
    except ValueError:
        await update.message.reply_text('⚠️ Por favor ingresa un número válido')
        return ESPERANDO_CANTIDAD_TRASPASO

# --- FUNCIONES PARA AÑADIR PRODUCTOS ---
async def iniciar_anadir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text('¿Qué producto quieres añadir?')
    return ESPERANDO_PRODUCTO_ANADIR

async def recibir_producto_anadir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['producto'] = update.message.text.lower()
    await update.message.reply_text('¿Cuántas unidades quieres añadir?')
    return ESPERANDO_CANTIDAD_ANADIR

async def recibir_cantidad_anadir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        cantidad = int(update.message.text)
        if cantidad <= 0:
            raise ValueError
        context.user_data['cantidad'] = cantidad
        await update.message.reply_text('¿Cuál es la cantidad mínima que quieres mantener de este producto? (0 para no alertar)')
        return ESPERANDO_MINIMO_ANADIR
    except ValueError:
        await update.message.reply_text('Por favor ingresa un número válido mayor a 0')
        return ESPERANDO_CANTIDAD_ANADIR

async def recibir_minimo_anadir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        minimo = int(update.message.text)
        if minimo < 0:
            raise ValueError
        context.user_data['minimo'] = minimo
        
        keyboard = [
            [InlineKeyboardButton("Nevera ❄️", callback_data='anadir_nevera')],
            [InlineKeyboardButton("Congelador 🧊", callback_data='anadir_congelador')],
            [InlineKeyboardButton("Despensa 🥫", callback_data='anadir_despensa')],
            [InlineKeyboardButton("Baño 🚿", callback_data='anadir_baño')],
            [InlineKeyboardButton("Trastero 📦", callback_data='anadir_trastero')],
            [InlineKeyboardButton("❌ Cancelar", callback_data='cancelar_anadir')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text('Selecciona ubicación:', reply_markup=reply_markup)
        return UBICACION_ANADIR
    except ValueError:
        await update.message.reply_text('Por favor ingresa un número válido (0 para no alertar)')
        return ESPERANDO_MINIMO_ANADIR

async def confirmar_anadir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ubicacion = query.data.split('_')[1]
    
    inventario = cargar_inventario()
    producto = context.user_data['producto']
    cantidad = context.user_data['cantidad']
    minimo = context.user_data['minimo']
    
    encontrado = False
    for item in inventario[ubicacion]:
        if item['nombre'] == producto:
            item['cantidad'] += cantidad
            item['minimo'] = minimo
            encontrado = True
            break
    
    if not encontrado:
        inventario[ubicacion].append({
            "nombre": producto,
            "cantidad": cantidad,
            "minimo": minimo
        })
    
    guardar_inventario(inventario)
    emoji = {'nevera': '❄️', 'congelador': '🧊', 'despensa': '🥫', 'baño': '🚿', 'trastero': '📦'}.get(ubicacion, '')
    
    mensaje = f'✅ Añadidas {cantidad} unidades de {producto.capitalize()} a la {ubicacion} {emoji}'
    if minimo > 0:
        mensaje += f'\n🔔 Alerta cuando queden {minimo} unidades'
    
    await query.message.reply_text(mensaje)
    
    lista_compra = generar_lista_compra(inventario)
    for item in lista_compra:
        if item['nombre'] == producto and item['ubicacion'] == ubicacion:
            await query.message.reply_text(
                f'⚠️ Atención: {producto.capitalize()} sigue estando por debajo del mínimo. '
                f'Considera añadir más unidades.'
            )
            break
    
    return ConversationHandler.END

# --- FUNCIONES PARA SACAR PRODUCTOS ---
async def iniciar_sacar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text('¿Qué producto quieres sacar?')
    return ESPERANDO_PRODUCTO_SACAR

async def recibir_producto_sacar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    producto_buscado = update.message.text.lower()
    inventario = cargar_inventario()
    ubicaciones = []
    
    for ubicacion, items in inventario.items():
        for item in items:
            if producto_buscado in item['nombre'].lower():
                ubicaciones.append(ubicacion)
                break
    
    if not ubicaciones:
        await update.message.reply_text('⚠️ No se encontraron coincidencias')
        return ConversationHandler.END
    
    context.user_data['producto'] = producto_buscado
    
    keyboard = []
    ubicaciones_unicas = list(set(ubicaciones))
    for ubicacion in ubicaciones_unicas:
        emoji = {'nevera': '❄️', 'congelador': '🧊', 'despensa': '🥫', 'baño': '🚿', 'trastero': '📦'}.get(ubicacion, '')
        keyboard.append([InlineKeyboardButton(f"{ubicacion.capitalize()} {emoji}", callback_data=f"sacar_{ubicacion}")])
    
    keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data='cancelar_sacar')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Selecciona ubicación:', reply_markup=reply_markup)
    return UBICACION_SACAR

async def recibir_ubicacion_sacar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ubicacion = query.data.split('_')[1]
    producto_buscado = context.user_data['producto']
    
    inventario = cargar_inventario()
    productos_en_ubicacion = []
    
    for item in inventario[ubicacion]:
        if producto_buscado in item['nombre'].lower():
            productos_en_ubicacion.append(item)
    
    if not productos_en_ubicacion:
        await query.message.reply_text('⚠️ Producto no encontrado')
        return ConversationHandler.END
    
    if len(productos_en_ubicacion) == 1:
        item = productos_en_ubicacion[0]
        context.user_data['producto_exacto'] = item['nombre']
        if item['cantidad'] > 1:
            context.user_data['ubicacion'] = ubicacion
            context.user_data['max_cantidad'] = item['cantidad']
            context.user_data['minimo_actual'] = item.get('minimo', 0)
            await query.message.reply_text(f'¿Cuántas unidades quieres sacar de {item["nombre"].capitalize()}? (Disponibles: {item["cantidad"]})')
            return ESPERANDO_CANTIDAD_SACAR
        else:
            inventario[ubicacion].remove(item)
            guardar_inventario(inventario)
            await query.message.reply_text(f'✅ Última unidad de {item["nombre"].capitalize()} sacada de la {ubicacion}')
            return ConversationHandler.END
    else:
        keyboard = [
            [InlineKeyboardButton(
                f"{item['nombre'].capitalize()} ({item['cantidad']} u.)", 
                callback_data=f"seleccionar_{ubicacion}_{item['nombre'].replace(' ', '_')}"
            )] 
            for item in productos_en_ubicacion
        ]
        keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data='cancelar_sacar')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text('Varios productos encontrados. Selecciona uno:', reply_markup=reply_markup)
        return ESPERANDO_SELECCION_PRODUCTO

async def seleccionar_producto_sacar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        _, ubicacion, producto = query.data.split('_', 2)
        producto = producto.replace('_', ' ')
        
        inventario = cargar_inventario()
        item_encontrado = None
        
        for item in inventario[ubicacion]:
            if item['nombre'] == producto:
                item_encontrado = item
                break
        
        if not item_encontrado:
            await query.message.reply_text('⚠️ Error: Producto no encontrado')
            return ConversationHandler.END
        
        context.user_data['producto_exacto'] = producto
        context.user_data['ubicacion'] = ubicacion
        
        if item_encontrado['cantidad'] > 1:
            context.user_data['max_cantidad'] = item_encontrado['cantidad']
            context.user_data['minimo_actual'] = item_encontrado.get('minimo', 0)
            await query.message.reply_text(
                f'¿Cuántas unidades quieres sacar de {producto.capitalize()}? '
                f'(Disponibles: {item_encontrado["cantidad"]})'
            )
            return ESPERANDO_CANTIDAD_SACAR
        else:
            inventario[ubicacion].remove(item_encontrado)
            guardar_inventario(inventario)
            await query.message.reply_text(f'✅ Última unidad de {producto.capitalize()} sacada de la {ubicacion}')
            return ConversationHandler.END
            
    except Exception as e:
        logger.error(f"Error en seleccionar_producto_sacar: {e}")
        await query.message.reply_text('⚠️ Error al procesar la selección')
        return ConversationHandler.END

async def confirmar_sacar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        cantidad = int(update.message.text)
        max_cantidad = context.user_data['max_cantidad']
        if cantidad <= 0 or cantidad > max_cantidad:
            raise ValueError
            
        ubicacion = context.user_data['ubicacion']
        producto = context.user_data['producto_exacto']
        minimo_actual = context.user_data['minimo_actual']
        
        inventario = cargar_inventario()
        for item in inventario[ubicacion]:
            if item['nombre'] == producto:
                item['cantidad'] -= cantidad
                if item['cantidad'] <= 0:
                    inventario[ubicacion].remove(item)
                break
        
        guardar_inventario(inventario)
        mensaje = f'✅ Sacadas {cantidad} unidades de {producto.capitalize()} de la {ubicacion}'
        
        if minimo_actual > 0 and item['cantidad'] <= minimo_actual:
            mensaje += f"\n⚠️ ¡Atención! {producto.capitalize()} ha alcanzado el mínimo ({minimo_actual})"
        
        await update.message.reply_text(mensaje)
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(f'Por favor ingresa un número entre 1 y {max_cantidad}')
        return ESPERANDO_CANTIDAD_SACAR

# --- FUNCIONES PARA BUSCAR PRODUCTOS ---
async def iniciar_buscar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text('🔍 ¿Qué producto buscas?')
    return ESPERANDO_PRODUCTO_BUSCAR

async def buscar_producto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    producto_buscado = update.message.text.lower()
    inventario = cargar_inventario()
    resultados = []
    
    for ubicacion, productos in inventario.items():
        for item in productos:
            if producto_buscado in item['nombre'].lower():
                emoji = {'nevera': '❄️', 'congelador': '🧊', 'despensa': '🥫', 'baño': '🚿', 'trastero': '📦'}.get(ubicacion, '')
                alerta = " ⚠️ (bajo mínimo)" if item['minimo'] > 0 and item['cantidad'] <= item['minimo'] else ""
                resultados.append(f"- {emoji} {ubicacion.capitalize()}: {item['nombre'].capitalize()} ({item['cantidad']}/{item['minimo']}){alerta}")
    
    if resultados:
        mensaje = "🔍 Resultados:\n" + "\n".join(resultados)
    else:
        mensaje = "⚠️ No se encontraron coincidencias"
    
    await update.message.reply_text(mensaje)
    return ConversationHandler.END

# --- FUNCIONES PARA MARCAR COMO COMPRADO ---
async def manejar_comprados(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    inventario = cargar_inventario()
    productos_bajo_minimo = [
        item for ubicacion in inventario.values() 
        for item in ubicacion 
        if item['minimo'] > 0 and item['cantidad'] <= item['minimo']
    ]
    
    if not productos_bajo_minimo:
        await query.message.reply_text("✅ No hay productos en la lista de compra")
        return
    
    keyboard = [
        [InlineKeyboardButton(
            f"{item['nombre'].capitalize()} (❄️ {item['cantidad']}/{item['minimo']})",
            callback_data=f"comprar_{item['nombre']}"
        )]
        for item in productos_bajo_minimo
    ]
    keyboard.append([InlineKeyboardButton("✅ Marcar TODO como comprado", callback_data='comprar_todo')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("Selecciona qué productos has comprado:", reply_markup=reply_markup)

async def procesar_compra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    inventario = cargar_inventario()
    data = query.data.split('_')
    
    if data[1] == 'todo':
        for ubicacion in inventario.values():
            for item in ubicacion:
                if item['minimo'] > 0 and item['cantidad'] <= item['minimo']:
                    item['cantidad'] = item['minimo'] + 1
        mensaje = "✅ Todos los productos marcados como comprados"
    else:
        producto = data[1]
        encontrado = False
        
        for ubicacion in inventario.values():
            for item in ubicacion:
                if item['nombre'] == producto and item['minimo'] > 0 and item['cantidad'] <= item['minimo']:
                    item['cantidad'] = item['minimo'] + 1
                    encontrado = True
                    break
            if encontrado:
                break
        
        mensaje = f"✅ {producto.capitalize()} marcado como comprado" if encontrado else "⚠️ Producto no encontrado"
    
    guardar_inventario(inventario)
    await query.message.reply_text(mensaje)

# --- FUNCIONES DE CANCELACIÓN ---
async def cancelar_operacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text('❌ Operación cancelada')
    return ConversationHandler.END

async def ver_registro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USER_IDS:
        await update.message.reply_text("⛔ No autorizado")
        return
    
    try:
        with open(REGISTRO_FILE, 'r', encoding='utf-8') as f:
            lineas = f.readlines()
        
        if not lineas:
            await update.message.reply_text("📜 El registro está vacío")
            return
        
        mensaje = "📜 **Últimas acciones**:\n" + "".join(lineas[-10:])
        await update.message.reply_text(mensaje)
    except FileNotFoundError:
        await update.message.reply_text("📜 No hay registros aún")

# --- MENÚ PRINCIPAL ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ALLOWED_USER_IDS:
        await update.message.reply_text("⛔ No autorizado")
        return
    
    keyboard = [
        [InlineKeyboardButton("➕ Añadir producto", callback_data='anadir')],
        [InlineKeyboardButton("➖ Sacar producto", callback_data='sacar')],
        [InlineKeyboardButton("🔄 Traspasar producto", callback_data='traspasar')],
        [InlineKeyboardButton("📦 Ver inventario", callback_data='inventario')],
        [InlineKeyboardButton("🔎 Buscar producto", callback_data='buscar')],
        [InlineKeyboardButton("🛒 Lista de la compra", callback_data='lista_compra')],
        [InlineKeyboardButton("✅ Marcar comprado", callback_data='marcar_comprado')],
        [InlineKeyboardButton("📜 Registro", callback_data='ver_registro')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('🏠 Menú principal:', reply_markup=reply_markup)

async def volver_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("➕ Añadir producto", callback_data='anadir')],
        [InlineKeyboardButton("➖ Sacar producto", callback_data='sacar')],
        [InlineKeyboardButton("🔄 Traspasar producto", callback_data='traspasar')],
        [InlineKeyboardButton("📦 Ver inventario", callback_data='inventario')],
        [InlineKeyboardButton("🔎 Buscar producto", callback_data='buscar')],
        [InlineKeyboardButton("🛒 Lista de la compra", callback_data='lista_compra')],
        [InlineKeyboardButton("✅ Marcar comprado", callback_data='marcar_comprado')],
        [InlineKeyboardButton("📜 Registro", callback_data='ver_registro')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text('🏠 Menú principal:', reply_markup=reply_markup)
    return ConversationHandler.END

# --- CONFIGURACIÓN DEL BOT ---
def main():
    application = ApplicationBuilder().token(TOKEN).build()

    # Handlers de conversación
    conv_anadir = ConversationHandler(
        entry_points=[CallbackQueryHandler(iniciar_anadir, pattern='^anadir$')],
        states={
            ESPERANDO_PRODUCTO_ANADIR: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_producto_anadir)],
            ESPERANDO_CANTIDAD_ANADIR: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_cantidad_anadir)],
            ESPERANDO_MINIMO_ANADIR: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_minimo_anadir)],
            UBICACION_ANADIR: [
                CallbackQueryHandler(confirmar_anadir, pattern='^anadir_(nevera|congelador|despensa|baño|trastero)$'),
                CallbackQueryHandler(cancelar_operacion, pattern='^cancelar_anadir$')
            ]
        },
        fallbacks=[CommandHandler('cancel', cancelar_operacion)]
    )

    conv_sacar = ConversationHandler(
        entry_points=[CallbackQueryHandler(iniciar_sacar, pattern='^sacar$')],
        states={
            ESPERANDO_PRODUCTO_SACAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_producto_sacar)],
            UBICACION_SACAR: [
                CallbackQueryHandler(recibir_ubicacion_sacar, pattern='^sacar_(nevera|congelador|despensa|baño|trastero)$'),
                CallbackQueryHandler(cancelar_operacion, pattern='^cancelar_sacar$')
            ],
            ESPERANDO_SELECCION_PRODUCTO: [
                CallbackQueryHandler(seleccionar_producto_sacar, pattern='^seleccionar_'),
                CallbackQueryHandler(cancelar_operacion, pattern='^cancelar_sacar$')
            ],
            ESPERANDO_CANTIDAD_SACAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirmar_sacar)]
        },
        fallbacks=[CommandHandler('cancel', cancelar_operacion)]
    )

    conv_traspaso = ConversationHandler(
        entry_points=[CallbackQueryHandler(iniciar_traspaso, pattern='^traspasar$')],
        states={
            ESPERANDO_UBICACION_ORIGEN: [
                CallbackQueryHandler(seleccionar_origen_traspaso, pattern='^traspaso_origen_(nevera|congelador|despensa|baño|trastero)$'),
                CallbackQueryHandler(cancelar_operacion, pattern='^cancelar_traspaso$')
            ],
            ESPERANDO_UBICACION_DESTINO: [
                CallbackQueryHandler(seleccionar_destino_traspaso, pattern='^traspaso_destino_(nevera|congelador|despensa|baño|trastero)$'),
                CallbackQueryHandler(cancelar_operacion, pattern='^cancelar_traspaso$')
            ],
            ESPERANDO_PRODUCTO_SACAR: [
                CallbackQueryHandler(seleccionar_producto_traspaso, pattern='^seleccionar_traspaso_'),
                CallbackQueryHandler(cancelar_operacion, pattern='^cancelar_traspaso$')
            ],
            ESPERANDO_CANTIDAD_TRASPASO: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirmar_traspaso)]
        },
        fallbacks=[CommandHandler('cancel', cancelar_operacion)]
    )

    conv_buscar = ConversationHandler(
        entry_points=[CallbackQueryHandler(iniciar_buscar, pattern='^buscar$')],
        states={
            ESPERANDO_PRODUCTO_BUSCAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, buscar_producto)]
        },
        fallbacks=[CommandHandler('cancel', cancelar_operacion)]
    )

    # Handlers principales
    application.add_handler(CommandHandler('start', start))
    application.add_handler(conv_anadir)
    application.add_handler(conv_sacar)
    application.add_handler(conv_traspaso)
    application.add_handler(conv_buscar)
    
    # Handlers de inventario
    application.add_handler(CallbackQueryHandler(mostrar_menu_inventario, pattern='^inventario$'))
    application.add_handler(CallbackQueryHandler(lambda update, _: mostrar_inventario(update, 'nevera'), pattern='^ver_nevera$'))
    application.add_handler(CallbackQueryHandler(lambda update, _: mostrar_inventario(update, 'congelador'), pattern='^ver_congelador$'))
    application.add_handler(CallbackQueryHandler(lambda update, _: mostrar_inventario(update, 'despensa'), pattern='^ver_despensa$'))
    application.add_handler(CallbackQueryHandler(lambda update, _: mostrar_inventario(update, 'baño'), pattern='^ver_baño$'))
    application.add_handler(CallbackQueryHandler(lambda update, _: mostrar_inventario(update, 'trastero'), pattern='^ver_trastero$'))
    application.add_handler(CallbackQueryHandler(lambda update, _: mostrar_inventario(update), pattern='^ver_completo$'))
    application.add_handler(CallbackQueryHandler(lambda update, _: mostrar_lista_compra(update), pattern='^lista_compra$'))
    
    # Handlers adicionales
    application.add_handler(CallbackQueryHandler(manejar_comprados, pattern='^marcar_comprado$'))
    application.add_handler(CallbackQueryHandler(procesar_compra, pattern='^comprar_'))
    application.add_handler(CallbackQueryHandler(ver_registro, pattern='^ver_registro$'))
    application.add_handler(CallbackQueryHandler(volver_menu, pattern='^menu_principal$'))

    logger.info("✅ Bot iniciado correctamente")
    application.run_polling()

if __name__ == '__main__':
    main()