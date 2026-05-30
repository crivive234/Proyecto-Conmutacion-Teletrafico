# Guía GNS3 — Fase 5: Topología con c3660

## Resumen de la topología

```
[br-vlan10]──Cloud1──[fa0/0]                    [br-vlan10]
                      c3660    ──[fa1/0]──Cloud2──[br-vlan20]
                     ROUTER    ──[fa2/0]──Cloud3──[br-vlan30]

br-vlan10 (10.10.10.0/24) → detector, chatbot    ← VLAN VIDEO
br-vlan20 (10.20.20.0/24) → Minikube/SuperTuxKart ← VLAN DATOS
br-vlan30 (10.30.30.0/24) → Grafana, Prometheus   ← VLAN MGMT
```

---

## PASO 0 — Ejecutar el script de red primero

```bash
sudo bash scripts/phase5/setup_network.sh
```

Verifica que los bridges existen:
```bash
ip link show | grep br-vlan
```

Deberías ver: `br-vlan10`, `br-vlan20`, `br-vlan30`

---

## PASO 1 — Agregar la imagen c3660 a GNS3

1. Abre **GNS3 GUI**
2. Ve a **Edit → Preferences → Dynamips → IOS Routers**
3. Clic en **New**
4. Selecciona la imagen: `~/GNS3/images/IOS/c3660-a3jk9s-mz.124-25d.image`
5. Configuración del router:

| Campo | Valor |
|-------|-------|
| Name | c3660-proyecto |
| Platform | c3660 |
| RAM | 128 MB |
| NVRAM | 256 KB |

6. En la pestaña **Slots**, agrega módulos:
   - Slot 0: `NM-1FE-TX` → da **fa0/0**
   - Slot 1: `NM-1FE-TX` → da **fa1/0**
   - Slot 2: `NM-1FE-TX` → da **fa2/0**

7. **Calcular Idle PC** (importante para no saturar la CPU):
   - Clic derecho en el router → **Idle PC**
   - Espera ~30 segundos
   - Selecciona el valor con asterisco `*` (mejor candidato)

8. Clic **OK** para guardar

---

## PASO 2 — Crear nuevo proyecto GNS3

1. **File → New blank project**
2. Nombre: `proyecto-fase5`
3. Clic **OK**

---

## PASO 3 — Agregar el router c3660

1. En el panel izquierdo, selecciona la pestaña de **Routers** (ícono de router)
2. Arrastra `c3660-proyecto` al canvas

---

## PASO 4 — Agregar nodos Cloud (uno por VLAN)

Los nodos Cloud conectan GNS3 con los bridges reales del host.

1. En el panel izquierdo, selecciona **End Devices** (ícono de PC)
2. Arrastra **3 nodos Cloud** al canvas
3. Nombra los clouds:
   - `Cloud-VIDEO` (VLAN 10)
   - `Cloud-DATOS` (VLAN 20)
   - `Cloud-MGMT`  (VLAN 30)

4. Configura cada Cloud:
   - Clic derecho en `Cloud-VIDEO` → **Configure**
   - En la pestaña **Ethernet**, agrega la interfaz: `br-vlan10`
   - Clic **Add** → **OK**
   - Repite para `Cloud-DATOS` → `br-vlan20`
   - Repite para `Cloud-MGMT` → `br-vlan30`

---

## PASO 5 — Conectar cables

Usa la herramienta de cable (ícono de cable en la barra de herramientas):

| Desde | Puerto | Hasta | Puerto |
|-------|--------|-------|--------|
| c3660 | fa0/0 | Cloud-VIDEO | br-vlan10 |
| c3660 | fa1/0 | Cloud-DATOS | br-vlan20 |
| c3660 | fa2/0 | Cloud-MGMT  | br-vlan30 |

---

## PASO 6 — Iniciar el router

1. Clic derecho en el c3660 → **Start**
2. Espera ~30 segundos a que arranque IOS
3. Clic derecho → **Console** para abrir la terminal

---

## PASO 7 — Pegar la configuración IOS

En la consola del c3660, pega el contenido de `scripts/phase5/router_config.ios`.

Puedes hacerlo en bloques. Verifica al final:

```
Router# show ip interface brief
Interface          IP-Address      OK? Method Status  Protocol
FastEthernet0/0    10.10.10.1      YES manual up      up
FastEthernet1/0    10.20.20.1      YES manual up      up
FastEthernet2/0    10.30.30.1      YES manual up      up
```

---

## PASO 8 — Verificar conectividad

Desde tu terminal en Arch Linux:

```bash
# Ping al router desde el host (a través de cada bridge)
ping -c 3 -I br-vlan10 10.10.10.1   # VLAN VIDEO
ping -c 3 -I br-vlan20 10.20.20.1   # VLAN DATOS
ping -c 3 -I br-vlan30 10.30.30.1   # VLAN MGMT

# Verificar rutas
ip route show | grep "br-vlan"
```

---

## PASO 9 — Captura de tráfico con Wireshark desde GNS3

1. Clic derecho en cualquier cable del canvas
2. Selecciona **Start capture**
3. GNS3 abre Wireshark automáticamente con la captura en ese enlace

### Filtros de Wireshark para el proyecto:

```
# Stream YOLO (MJPEG)
tcp.port == 8000

# Chat con el asistente
tcp.port == 8001

# Tráfico SuperTuxKart
udp && (udp.port >= 7000 && udp.port <= 8000)

# Grafana
tcp.port == 3000

# DSCP marcado por QoS
ip.dsfield.dscp == 34    ← AF41 (VIDEO)
ip.dsfield.dscp == 18    ← AF21 (DATOS)
ip.dsfield.dscp == 16    ← CS2  (MGMT)
```

---

## PASO 10 — Verificar QoS en el router

En la consola del c3660:

```
show policy-map interface FastEthernet0/0
show class-map
show ip access-lists
```

La salida de `show policy-map` muestra los contadores de paquetes clasificados por clase — esa es la evidencia de que QoS está funcionando.

---

## Guardar topología

**File → Save project** — guarda el `.gns3` del proyecto para reutilizarlo.

---

## Comandos útiles en el router

```
! Ver estado de interfaces
show ip interface brief

! Ver rutas
show ip route

! Ver estadísticas QoS
show policy-map interface

! Ver ACLs con contadores de hits
show access-lists

! Ver tabla ARP
show arp

! Debug tráfico (usar con cuidado)
debug ip packet detail
```
