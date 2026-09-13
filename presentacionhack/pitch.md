# Pitch para el deck de Rehar

Duración estimada: 2 minutos y medio. Cada bloque corresponde a una lámina del PDF.

## Guion oral

**2. Dos millones de toneladas**
Dos millones de toneladas de mani es lo que produce la argetina en un año....

Bueno, lo que acabo de decir es mentira. 
pero podria llegar a ser verdad. 

en realidad el numero real es 1,8 millones de toneladas. Esto nos lleva a preguntarnos, en donde esta la diferencia? 
 ¿qué quedó en el suelo después de cosechar?

**4. Pérdidas de ocho a diez por ciento**

En un lote donde se pierde entre ocho y diez por ciento, hay vainas que ya se produjeron y no llegaron a la tolva. 

La planta de mani crece debajo de la tierra, el proceso de cosecha implica el arrancado y zarandeao de la misma, en este proceso cientos de vahinas caen al suelo. 

Estamos hablando de numeros astronomicos.

Si consideramos un rinde promedio de 3000kg pH y asumimos un 10% de eso se pierde , en un campo de 500Hs estamos hablando de 60 toneladas de perdidas.  45mil USD olvidaddos en la tierra. 


**5. Cosecha del maní — la solución**

Ahí entra Rehar. Una solucion automatizada que viene a terminar con esta perdida. Como?? ahora se lo mostramos!

Desarrollamos un sistema capaz de recorrer el terreno, observar la superficie con una cámara y detectar automáticamente las vainas de maní
mediante visión artificial. La información se procesa en tiempo real y permite identificar zonas con mayores pérdidas, contar vainas y estimar el volumen recuperable por hectárea.

El prototipo utiliza un robot móvil, una cámara convencional y un modelo de inteligencia artificial entrenado específicamente para detectar
  vainas de maní en condiciones reales de suelo, rastrojo e iluminación.

El valor para el productor es concreto: más información, menos desperdicio y mejores decisiones sobre la regulación de la maquinaria y la
recuperación del producto perdido.
 Una cámara montada en nuestro prototipo móvil observa el suelo. El celular envía las imágenes a un backend con un modelo YOLO, que señala las vainas visibles. En la pantalla vemos el video procesado y una estimación demostrativa de la pérdida, en tiempo real. Ese flujo ya funciona. El mapa anticipa cómo llevar la medición a cada zona del lote; la recuperación automática sería la siguiente etapa.


**7. El productor**

Nuestro primer cliente es el productor que necesita ver lo que quedó, estimar la pérdida superficial y tomar mejores decisiones para su próxima campaña.

**8. Las empresas**

También las empresas que gestionan muchos lotes: un mapa comparable les permitiría priorizar recorridos, ajustar la cosecha y concentrar recursos donde haya más oportunidad.

**9. Cierre — próxima campaña**

 No buscamos reemplazar una cosechadora. Buscamos hacer visible lo que hoy se pierde y convertir datos del campo en valor económico.. Rehar empieza haciendo visible lo que hoy queda en el suelo. Queremos llevar este prototipo al campo con productores y empresas, validar la medición y avanzar hacia la recuperación de las vainas. En la próxima campaña, contá con Rehar.

## Ajustes recomendados antes de presentar

- Las láminas 2 y 3 dicen, ambas, «toneladas de maní cosechadas por año». Los 1,8 millones corresponden a la campaña 2024/25 según la [Secretaría de Agricultura](https://www.argentina.gob.ar/noticias/record-de-produccion-y-exportaciones-de-mani). Conviene presentar los dos millones como una cifra redondeada de escala, no como una cosecha adicional ni como base para calcular pérdidas.
- La lámina 4 presenta el 8 % al 10 % como pérdida general. El guion lo trata como un escenario posible; conviene indicar la fuente y aclarar a qué etapa de cosecha y condiciones corresponde.
- En la lámina 6, 300 kg/ha multiplicados por 500 ha son **150 toneladas**, no 60. El guion hace explícito que las 60 toneladas representan otro escenario: 120 kg/ha, equivalente al 4 % de un rinde de 3.000 kg/ha. Conviene aclararlo también en la lámina. Los USD 45.000 suponen USD 750 por tonelada; el precio requiere fecha y fuente.
- El PDF usa **Rehar** y la aplicación web usa **Rehearves**. Unificar la marca antes de mostrar ambos materiales.
- Si se usa [index.html](index.html) para proyectar el deck, su constante `PDF_FILE` apunta a un nombre sin «(1)», distinto del archivo presente en esta carpeta.
