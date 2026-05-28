from fastapi import FastAPI, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import requests
from PIL import Image
import io
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# HELPERS
# =========================

def geo_box_to_pixels(bounds, regional_bounds, canvas_width, canvas_height):
    south, west = bounds[0]
    north, east = bounds[1]

    x1 = int((west - regional_bounds["west"]) / (regional_bounds["east"] - regional_bounds["west"]) * canvas_width)
    x2 = int((east - regional_bounds["west"]) / (regional_bounds["east"] - regional_bounds["west"]) * canvas_width)

    y1 = int((regional_bounds["north"] - north) / (regional_bounds["north"] - regional_bounds["south"]) * canvas_height)
    y2 = int((regional_bounds["north"] - south) / (regional_bounds["north"] - regional_bounds["south"]) * canvas_height)

    return x1, y1, x2 - x1, y2 - y1


def paste_geo(canvas, image, image_bounds, regional_bounds):
    canvas_width, canvas_height = canvas.size

    x, y, width, height = geo_box_to_pixels(
        image_bounds,
        regional_bounds,
        canvas_width,
        canvas_height
    )

    image = image.resize((width, height))
    canvas.alpha_composite(image, (x, y))


def keep_radar_colors_only(img):
    img = img.convert("RGBA")
    pixels = img.load()
    width, height = img.size

    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]

            is_radar = (
                (b > 120 and g > 80) or
                (g > 120 and b > 60) or
                (r > 140 and g > 80)
            )

            if not is_radar:
                pixels[x, y] = (0, 0, 0, 0)

    return img


def remove_dark_background(img):
    img = img.convert("RGBA")
    pixels = img.load()
    width, height = img.size

    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]

            if r < 35 and g < 35 and b < 35:
                pixels[x, y] = (0, 0, 0, 0)

    return img


# =========================
# EL SALVADOR FRAME LIST
# =========================

@app.post("/el-salvador/list")
@app.get("/el-salvador/list")
def el_salvador_list():
    url = "https://radar.ambiente.gob.sv/listJSON.php"

    r = requests.post(url, timeout=15)

    return Response(
        content=r.content,
        media_type="application/json"
    )


# =========================
# EL SALVADOR CLEANED IMAGE
# =========================

@app.get("/el-salvador/image")
def el_salvador_image(filename: str = Query(...)):
    url = f"https://radar-cdn.snet.gob.sv/esa8/Images/60km/{filename}"

    r = requests.get(url, timeout=15)

    img = Image.open(io.BytesIO(r.content)).convert("RGBA")
    img = remove_dark_background(img)

    output = io.BytesIO()
    img.save(output, format="PNG")

    return Response(
        content=output.getvalue(),
        media_type="image/png"
    )


# =========================
# BELIZE RADAR API CATALOG
# =========================

@app.get("/belize/radar-images")
def belize_radar_images():
    browser_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://nms.gov.bz/sensors/radar-imagery/",
    }

    config_response = requests.get(
        "https://nms.gov.bz/config.php",
        headers=browser_headers,
        timeout=15
    )

    config = config_response.json()

    token = config["AUTH_TOKEN"]
    api_url = config["WIMP3_HOST"] + "/api/radar-images/"

    api_headers = {
        "Authorization": "Token " + token,
        "User-Agent": browser_headers["User-Agent"],
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://nms.gov.bz/sensors/radar-imagery/",
        "Origin": "https://nms.gov.bz",
    }

    api_response = requests.get(
        api_url,
        headers=api_headers,
        timeout=15
    )

    return Response(
        content=api_response.content,
        status_code=api_response.status_code,
        media_type="application/json"
    )


# =========================
# BELIZE CLEANED 400 KM IMAGE
# =========================

@app.get("/belize/400km")
def belize_400km():
    image_url = "https://nms.gov.bz/images/radar/Recent_400km_pic.gif"

    r = requests.get(
        image_url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://nms.gov.bz/sensors/radar-imagery/"
        },
        timeout=15
    )

    img = Image.open(io.BytesIO(r.content)).convert("RGBA")

    width, height = img.size

    # Crop out right-side legend/info panel
    img = img.crop((0, 0, int(width * 0.78), height))

    img = keep_radar_colors_only(img)

    output = io.BytesIO()
    img.save(output, format="PNG")

    return Response(
        content=output.getvalue(),
        media_type="image/png"
    )


# =========================
# GEOGRAPHIC MOSAIC
# =========================

@app.get("/mosaic/caribbean")
def mosaic_caribbean():
    canvas_width = 1400
    canvas_height = 900

    regional_bounds = {
        "south": 10.0,
        "north": 22.0,
        "west": -93.0,
        "east": -83.0
    }

    canvas = Image.new(
        "RGBA",
        (canvas_width, canvas_height),
        (0, 0, 0, 0)
    )

    # -------------------------
    # Belize layer
    # -------------------------

    belize_url = "https://nms.gov.bz/images/radar/Recent_400km_pic.gif"

    belize_response = requests.get(
        belize_url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://nms.gov.bz/sensors/radar-imagery/"
        },
        timeout=15
    )

    belize = Image.open(io.BytesIO(belize_response.content)).convert("RGBA")

    bw, bh = belize.size
    belize = belize.crop((0, 0, int(bw * 0.78), bh))
    belize = keep_radar_colors_only(belize)

    belize_bounds = [
        [14.00, -92.00],
        [21.30, -84.60]
    ]
    paste_geo(
        canvas,
        belize,
        belize_bounds,
        regional_bounds
    )
@app.get("/san-andres/z")
def san_andres_z():
    url = "https://bart.ideam.gov.co/ospa/gifs/Radar/Transp/San_Andres/San_Andres_z.gif"

    r = requests.get(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        },
        timeout=15
    )

    return Response(
        content=r.content,
        media_type="image/gif"
    )
@app.get("/cocesna/times")
def cocesna_times():
    url = "http://rainweb.cocesna.org:8080/geoserver/wms?service=WMS&request=GetCapabilities"

    r = requests.get(url, timeout=20)
    text = r.text

    start = text.find('<Name>geosolutions:LNB_CAPPI_Z_450Km_1Km_cappi_dBZ</Name>')
    if start == -1:
        return {"times": []}

    section = text[start:start + 20000]

    dim_start = section.find('<Dimension name="time"')
    if dim_start == -1:
        return {"times": []}

    close_start = section.find(">", dim_start)
    close_end = section.find("</Dimension>", close_start)

    times_text = section[close_start + 1:close_end].strip()
    times = [t.strip() for t in times_text.split(",") if t.strip()]

    return {
        "times": times,
        "latest": times[-1] if times else None
    }
    # -------------------------
    # El Salvador layer
    # -------------------------

    es_list = requests.post(
        "https://radar.ambiente.gob.sv/listJSON.php",
        timeout=15
    ).text

    fixed = (
        es_list
        .replace("imagen:", '"imagen":')
        .replace("'", '"')
    )

    frames = json.loads(fixed)
    latest = frames[0]["imagen"]

    es_url = f"https://radar-cdn.snet.gob.sv/esa8/Images/60km/{latest}"

    es_response = requests.get(es_url, timeout=15)

    es = Image.open(io.BytesIO(es_response.content)).convert("RGBA")
    es = remove_dark_background(es)

    el_salvador_bounds = [
        [12.705, -90.286],
        [14.704, -87.560]
    ]

    paste_geo(
        canvas,
        es,
        el_salvador_bounds,
        regional_bounds
    )

    output = io.BytesIO()
    canvas.save(output, format="PNG")

    return Response(
        content=output.getvalue(),
        media_type="image/png"
    )
app.mount("/", StaticFiles(directory="static", html=True), name="static")