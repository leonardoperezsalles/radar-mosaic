# Radar Mosaic Version 1 — Image/Tile Overlay

This is the simplest Barbados-style radar mosaic prototype.

It does **not** decode raw radar files. It uses a public radar tile source, overlays radar tiles on a Leaflet map, and animates recent frames.

## How to run on Windows

1. Unzip this folder.
2. Double-click `index.html`.

If your browser blocks API requests from a local file, run a tiny local server:

```powershell
cd C:\path\to\radar-mosaic-version1
python -m http.server 8000
```

Then open:

```text
http://localhost:8000
```

## What this teaches

This reproduces the frontend concept:

- map base layer
- radar mosaic tile layer
- frame animation
- opacity control
- timestamp display

## Next upgrade

Replace the RainViewer tile URL with your own generated tile set:

```text
/tiles/{timestamp}/{z}/{x}/{y}.png
```

That is the point where it becomes your own BarbadosWeather-style system.
