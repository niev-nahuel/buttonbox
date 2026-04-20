import usb_cdc

# Solo el puerto consola (ACM0) — evita confusión con dos puertos.
# El firmware envía eventos con print() por este mismo puerto.
usb_cdc.enable(console=True, data=False)
