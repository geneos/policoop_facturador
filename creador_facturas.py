# -*' coding: utf8 -*-

#COMPANY NAME
#Sierra: "COOPERSIVE LTDA."
#Puan: "COOPERATIVA DE SERVICIOS Y OBRAS PUBLICAS LTDA DE PUAN"
#San Manuel: "COOPERATIVA ELECTRICA DE SMA"

import sys
import os
from trytond.pool import Pool
from decimal import Decimal, ROUND_DOWN, ROUND_UP, ROUND_HALF_UP
from trytond.transaction import Transaction
import datetime
import math
import psycopg2
REQUERIDO = True


conn = psycopg2.connect(host='localhost' ,dbname='arba', user='tryton',
	password='tryton')
cur = conn.cursor()


class CreadorFacturas(object):
	def __init__(self, fecha_emision_factura):
		self.cantidad_facturas_creadas = 0
		self.fecha_emision_factura = fecha_emision_factura		
	''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
	'''FUNCIONES GENERALES '''
	''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
	def calcular_unit_price(self, quantity, product, price_list, customer, dias_lectura=None):
		return product.get_sale_price([product], quantity)[product.id]
	
	def buscar(self, modelo, atributo, valor):
		search = modelo.search([atributo, '=', valor])
		if search:
			return search[0]
		else:
			return None

	def get_subtotal_cargos(self, sale, tipo, servicio):
		"""
		Retornamos el subtotal de los cargos
		"""
		subtotal_cargos = 0
		if sale.lines:
			for line in sale.lines:
				if line.servicio == servicio:
					if line.type == 'line' and line.product.tipo_producto == tipo:
						if not line.product.sin_subsidio and not line.product.ocultar_en_impresion:
							subtotal_cargos += Decimal(line.amount).quantize(Decimal(".01"), rounding=ROUND_DOWN)
							
		return subtotal_cargos

	
	def buscar_pos(self):
		"""
		Buscamos el punto de venta que vamos a usar para las facturas.
		Este punto de venta deberia tener un PosSequence para cada tipo de factura (ver INVOICE_TYPE_AFIP_CODE
		en account_invoice_ar/invoice.py).
		"""
		Pos = Pool().get('account.pos')
		pos = Pos.search([('pos_type', '=', 'electronic'), ('number', '=', 1)]) 
		return pos[0]
		
		
	''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
	'''FUNCIONES QUE CREAN LINEAS'''
	''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
	
	#Todas las otras funciones crean con esta funcion
	#Creo la columna servicio, para usar despues en el reporte
	def crear_sale_line(self, amount, product, unit_price, sequence):
		"""
		Creamos una linea de ventas de acuerdo a los parametros que recibimos.
		"""
		
		SaleLine = Pool().get('sale.line')
		new_line = SaleLine(
				product=product,
				quantity=Decimal(round(amount,2)),
				description=product.name,
				unit=product.default_uom,
				unit_price = Decimal(unit_price),
				sequence = sequence,				
				)

		return new_line

	
	def crear_sale_lines_independientes_consumo(self, party, product_name):
		ret = []
		#Obtenemos los productos que son cargos fijos, de la lista de precios que recibimos como parametro
		filtro_producto = lambda x: (x.product.name == product_name)
		productos = map(lambda x: x.product, filter(filtro_producto))
		for producto in productos:					
			#Le agrego la sequence = 1 para cargos fijos
			up = producto.list_price
			ret.append(
				self.crear_sale_line(1, producto, up 1)
			)
		return ret
		

	
	''''''''''''''''''''''''''''''''''''''
	'''FUNCION MADRE QUE CREA LA VENTA'''
	''''''''''''''''''''''''''''''''''''''

	def crear_venta_padre(self, insurance_id):
		insurance = Pool().get('gnuhealth.insurance')(insurance_id)				
		Invoice = Pool().get('account.invoice')		
		#Chequeo que no haya factura de ese asegurado, posteada, con esa fecha
		invoice_facturada = Invoice.search([('date','=', self.fecha_emision_factura), ('insurance','=',insurance_id), ('state','=','posted')])

		if not invoice_facturada:
						
			#VENTA
			Sale = Pool().get('sale.sale')
			party = insurance.name
			pos = self.buscar_pos()
				
			with Transaction().set_context({"customer": party}):
				#Creamos la venta a la que le vamos a asociar las lineas de venta
				descripcion = str(insurance.name.encode('utf-8')) + " - " + str(insurance.plan_id.name.encode('utf-8'))
				sale = Sale(
						party = insurance.name,						
						description = descripcion,
						pos = pos
				)
				#Creamos las lineas para los distintos tipos de productos
				sale_lines = []

				#1 Cargos Fijos				
				#Las lineas que no dependen del consumo, solo se crean una vez por venta
				sale_lines.extend(self.crear_sale_lines_independientes_consumo(party, insurance.plan_id.name))
				sale.lines = sale_lines
				sale.save()
				sale_lines = []															
			
							
				#IMPUESTOS - SE LLAMA UNA SOLA VEZ
				#Aplicamos los impuestos que correspondan a cada linea de venta y los del suministro-usuarios
				Tax = Pool().get('account.tax')
				for i in sale.lines:
					#Revisar CAMPO exento_leyes_prov para no agregar leyes provinciales
					up = i.unit_price
					tax_ids = i.on_change_product().get("taxes")#lista de ids					
					i.unit_price = up
					tax_browse_records = Tax.browse(tax_ids) or []
					i.taxes = tuple(tax_browse_records)
					i.save()
				
				#Avanzamos a presupuesto
				sale.invoice_address = sale.party.address_get(type='invoice')
				sale.shipment_address = sale.party.address_get(type='delivery')
				sale.quote([sale])
				#Avanzamos a confirmado
				sale.confirm([sale])

				#Controlo que no sea menor a cero el total
				if sale.total_amount >= Decimal('0'):
					#Avanzamos a procesado. En este estado se crea la factura
					#de la venta.					    					
					sale.process([sale])
					#Luego de ejecutar el workflow de la venta, la guardamos.
					sale.save()							
					#Seteamos las fechas de creacion, vencimiento de la factura y recargo por vencimiento.
					#Tambien seteamos el suministro.
					hoy = datetime.date.today()
					if sale.invoices:
						#import pudb;pu.db
						sale.invoices[0].invoice_date = self.fecha_emision_factura						
						sale.invoices[0].pos = pos												
						#Revisar
						invoice_type_ret = sale.invoices[0].on_change_pos()["invoice_type"]						
						sale.invoices[0].invoice_type = sale.invoices[0].on_change_pos()["invoice_type"]											
						
						#QUEDA EN BORRADOR
																					
						Transaction().cursor.commit()				

				self.actualizar_resumen_importacion(sale)

		return True
		