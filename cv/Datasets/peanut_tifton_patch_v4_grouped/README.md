# Dataset reorganizado

División COCO 70/15/15 agrupada por captura base para impedir que parches o
augmentations de una misma captura aparezcan en más de una partición.

| Split | Capturas base | Imágenes | Anotaciones |
| --- | ---: | ---: | ---: |
| `train` | 14 | 412 | 44643 |
| `val` | 3 | 88 | 9572 |
| `test` | 3 | 88 | 9601 |

La asignación exacta y la estrategia utilizada están registradas en
`split_manifest.json`. Los archivos `_annotations.coco.json` fueron
regenerados con IDs consistentes para cada split.

Este es el único dataset local conservado. La descarga original fue eliminada
después de verificar que las 588 imágenes y 63.816 anotaciones estuvieran
presentes en esta reorganización. Su procedencia quedó registrada en
`cv/contexto_entrenamiento.md` y en `split_manifest.json`.

> Nota: la versión descargada ya contiene augmentations. Esta división agrupada
> es la alternativa más segura con los archivos disponibles. Para una evaluación
> más rigurosa, se deben dividir primero las imágenes originales por captura y
> aplicar augmentations únicamente a `train`, no a `val` ni a `test`.
