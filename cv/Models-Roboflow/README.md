# Modelos entrenados con el dataset de Roboflow

`train_yolo26.py` guarda aquí una carpeta por corrida con checkpoints, métricas,
logs, configuración, entorno y manifiesto del subset utilizado.

Los artefactos generados se ignoran en Git porque los pesos y gráficos pueden ser
grandes. La excepción es `yolo26m-peanut-own-finetune-v1/weights/best.pt`,
incluido para reproducir la inferencia de la aplicación web. Los demás
resultados permanecen disponibles localmente en esta carpeta.
