@echo off
setlocal
cd /d "%~dp0"

rem ---- settings ----
set "BUILD=build"
set "MC_DIR=OsmAndMapCreator-main"
set "REGION=west_flanders.geojson"
set "BASE_URL=https://tiles1.squadrats.com/fiwoOW0G6oZ5Hn0eeR1TeHgc7lU2/trophies/1754233411401/{z}/{x}/{y}.pbf"
set "Z=12"
set "LAYER=squadratinhos"

if not exist "%BUILD%" mkdir "%BUILD%"

rem clean previous outputs (safe)
del /f /q "%BUILD%\*.gpkg" "%BUILD%\*.geojson" "%BUILD%\*.osm" "%BUILD%\*.obf" 2>nul

echo [1] fetch to "%BUILD%\%LAYER%.gpkg"
python fetch_tiles_west_flanders.py ^
  --base-url "%BASE_URL%" ^
  --region-geojson "%REGION%" ^
  --z-fetch %Z% ^
  --layer "%LAYER%" ^
  --out "%BUILD%\%LAYER%.gpkg" ^
  --promote-multi

echo [2] makevalid to "%BUILD%\%LAYER%_valid.gpkg"
ogr2ogr -f GPKG "%BUILD%\%LAYER%_valid.gpkg" "%BUILD%\%LAYER%.gpkg" -nlt PROMOTE_TO_MULTI -makevalid -nln "%LAYER%"

echo [3] gpkg to geojson (EPSG:4326)
ogr2ogr -f GeoJSON -t_srs EPSG:4326 "%BUILD%\%LAYER%_wgs84.geojson" "%BUILD%\%LAYER%_valid.gpkg" -nln "%LAYER%" -nlt PROMOTE_TO_MULTI

echo [4] geojson to osm (landuse=squadratinhos)
python geojson2osm_squadratinhos_ids_inc.py ^
  --in "%BUILD%\%LAYER%_wgs84.geojson" ^
  --out "%BUILD%\%LAYER%.osm" ^
  --no-default-index-tag ^
  --add-index-tag landuse=squadratinhos ^
  --duplicate-outer-tags

echo [5] osm to obf (MapCreator)
rem add Java to PATH if needed (edit if your JDK path differs)
set "JAVA_BIN=C:\Program Files\Eclipse Adoptium\jdk-17.0.16.8-hotspot\bin"
if exist "%JAVA_BIN%\java.exe" set PATH=%JAVA_BIN%;%PATH%

for %%F in ("%CD%\%BUILD%\%LAYER%.osm") do set "OSM_ABS=%%~fF"
for %%F in ("%CD%\%MC_DIR%\rendering_types_squadratinhos.xml") do set "TYPES_ABS=%%~fF"

pushd "%MC_DIR%"
call utilities.bat generate-map "%OSM_ABS%" --rendering-types="%TYPES_ABS%"
popd

echo Done. OBF: "%BUILD%\Squadratinhos.obf"
endlocal
