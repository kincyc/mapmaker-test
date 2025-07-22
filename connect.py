import os
import psycopg2
import site
import sys

# Inject venv + system paths
site.addsitedir("/home/ubuntu/mapmaker-test/.venv/lib/python3.10/site-packages")
sys.path.append("/usr/share/qgis/python")
sys.path.append("/usr/lib/python3/dist-packages")

from dotenv import load_dotenv
from qgis.core import (
    QgsApplication,
    QgsProject,
    QgsMapSettings,
    QgsCoordinateReferenceSystem,
    QgsRectangle,
    QgsMapRendererParallelJob,
    QgsPointXY,
)
from qgis.PyQt.QtGui import QImage, QPainter, QColor
from qgis.PyQt.QtCore import QSize

# -------------------------
# Load environment variables
# -------------------------
load_dotenv()

PG_PARAMS = {
    "host": os.getenv("PG_HOST"),
    "port": int(os.getenv("PG_PORT")),
    "dbname": os.getenv("PG_DBNAME"),
    "user": os.getenv("PG_USER"),
    "password": os.getenv("PG_PASSWORD"),
}

PROJECT_NAME = os.getenv("PROJECT_NAME", "WRR Images_mb")
PROJECT_PATH = f"/tmp/{PROJECT_NAME.replace(' ', '_')}.qgz"
OUTPUT_IMAGE = os.getenv("OUTPUT_IMAGE", "/tmp/rendered_map.png")

# These are in EPSG:3857 now — no need to transform
CENTER_X = float(os.getenv("CENTER_X", -13583211.8))  # formerly CENTER_LON
CENTER_Y = float(os.getenv("CENTER_Y", 4654056.0))  # formerly CENTER_LAT

SCALE = int(os.getenv("SCALE", 5000))
DPI = int(os.getenv("DPI", 96))
WIDTH = int(os.getenv("WIDTH", 1024))
HEIGHT = int(os.getenv("HEIGHT", 768))
LAYER_NAMES = ["Structure Footprints Pushpin", "USDA WRC 2024", "OpenStreetMap"]

# -------------------------
# Step 1: Extract QGIS Project from DB
# -------------------------
print(f"Connecting to DB to fetch project: {PROJECT_NAME}")
conn = psycopg2.connect(**PG_PARAMS)
cur = conn.cursor()

cur.execute(
    "SELECT content FROM application_qgis.qgis_projects WHERE name = %s",
    (PROJECT_NAME,),
)

row = cur.fetchone()
if not row:
    raise ValueError(f"No project found with name '{PROJECT_NAME}'")

with open(PROJECT_PATH, "wb") as f:
    f.write(row[0])
print(f"Project saved to: {PROJECT_PATH}")

cur.close()
conn.close()

# -------------------------
# Step 2: Initialize QGIS
# -------------------------
os.environ["QT_QPA_PLATFORM"] = "offscreen"
app = QgsApplication([], False)
app.setPrefixPath("/usr", True)
app.initQgis()

# Load project
project = QgsProject.instance()
if not project.read(PROJECT_PATH):
    raise Exception("Failed to load project")

# Filter layers
all_layers = project.mapLayers().values()
print(f"Found {len(all_layers)} layers in project")
print(f"Layer names: {[layer.name() for layer in all_layers]}")
layers = [
    layer for layer in all_layers if any(name in layer.name() for name in LAYER_NAMES)
]
if len(layers) < len(LAYER_NAMES):
    raise Exception("Not all required layers found")

# -------------------------
# Step 3: Set up map and render
# -------------------------
map_settings = QgsMapSettings()
map_settings.setLayers(layers)
map_settings.setOutputSize(QSize(WIDTH, HEIGHT))
map_settings.setBackgroundColor(QColor("white"))

# Use EPSG:3857 directly (you’re providing meters)
crs = QgsCoordinateReferenceSystem("EPSG:3857")
map_settings.setDestinationCrs(crs)

# Use provided center point (no CRS transform needed)
center_pt = QgsPointXY(CENTER_X, CENTER_Y)

# Calculate extent in meters
meters_per_pixel = SCALE / DPI * 0.0254
extent_width = WIDTH * meters_per_pixel
extent_height = HEIGHT * meters_per_pixel
extent = QgsRectangle(
    center_pt.x() - extent_width / 2,
    center_pt.y() - extent_height / 2,
    center_pt.x() + extent_width / 2,
    center_pt.y() + extent_height / 2,
)
map_settings.setExtent(extent)

# Render image
image = QImage(QSize(WIDTH, HEIGHT), QImage.Format_ARGB32_Premultiplied)
image.fill(0)
painter = QPainter(image)

job = QgsMapRendererParallelJob(map_settings)
job.start()
job.waitForFinished()
job.renderedImage().save(OUTPUT_IMAGE, "png")
painter.end()

print(f"Rendered image saved to: {OUTPUT_IMAGE}")
app.exitQgis()
