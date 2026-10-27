# 🐱 Control de Peso: Mei & Sami (Arenero Inteligente Tuya)

Servicio autónomo contenerizado para monitorizar y graficar el peso de Mei y Sami utilizando la API oficial de Tuya Cloud.

Incluye:
- **Sincronización en segundo plano**: Consulta las nuevas lecturas de peso periódicamente (cada 30 min por defecto).
- **Persistencia infinita**: Almacena todo el historial en SQLite (`cat_weights.db`), superando el límite de 7 días de Tuya.
- **Gráfica interactiva en tiempo real**: Web responsive con autoescala dinámica, filtros por gata (Mei / Sami / Parciales), tooltips y botón de forzar sincronización manual.
- **API interna**:
  - `GET /` -> Dashboard interactivo
  - `GET /data.json` -> Datos en formato JSON
  - `GET /api/sync` -> Dispara una sincronización manual inmediata
  - `GET /health` -> Healthcheck para Coolify / Docker

---

## 🚀 Despliegue en Coolify

Este repositorio está preparado para despliegue directo en **Coolify**:

1. En tu panel de Coolify, entra en tu proyecto y pulsa **+ New** -> **Application** -> **Public Repository** (o Private si está conectado con GitHub App).
2. Pega la URL del repositorio: `https://github.com/Franquinro/datostuya.git`
3. En **Build Pack**, Coolify detectará automáticamente el `Dockerfile` (o puedes seleccionar `Docker Compose`).
4. **Puertos**: Coolify expondrá el puerto `8080`.
5. *(Opcional)* En **Storage / Persistent Volumes**, añade un volumen persistente para no perder la base de datos al reconstruir el contenedor:
   - **Destination Path**: `/app/data`
6. Pulsa **Deploy**. ¡Y listo! Tu dominio o IP asignada tendrá el panel funcionando 24/7.

---

## ⚙️ Variables de Entorno (Opcionales)

El contenedor ya incluye las credenciales configuradas por defecto, pero puedes sobrescribirlas desde el panel de Coolify si lo deseas:

| Variable | Descripción | Valor por defecto |
| :--- | :--- | :--- |
| `PORT` | Puerto HTTP del servidor | `8080` |
| `SYNC_INTERVAL_MINUTES` | Intervalo de sincronización con Tuya | `30` |
| `TUYA_CLIENT_ID` | Access ID de Tuya OpenAPI | `h3ckrv4vgper9fgd4x4x` |
| `TUYA_SECRET` | Access Secret de Tuya OpenAPI | `8f1d6e8d57f84667a6e94e1fffa3d801` |
| `TUYA_BASE_URL` | Endpoint regional de Tuya | `https://openapi.tuyaeu.com` |
| `TUYA_DEVICE_ID` | ID del arenero en Tuya | `bf39a8ac3f20224c9535px` |

---

## 💻 Ejecución local con Docker (Opcional)

```bash
docker compose up -d --build
```
Abre en tu navegador: `http://localhost:8080`
