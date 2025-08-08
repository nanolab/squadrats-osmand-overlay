@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

rem ---- settings ----
set "BUILD=build"
set "MC_DIR=OsmAndMapCreator-main"
set "REGION=west_flanders.geojson"
set "BASE_URL=https://tiles1.squadrats.com/fiwoOW0G6oZ5Hn0eeR1TeHgc7lU2/trophies/1754233411401/{z}/{x}/{y}.pbf"
set "Z=12"

set "JAVA_BIN=C:\Program Files\Eclipse Adoptium\jdk-17.0.16.8-hotspot\bin"
if exist "%JAVA_BIN%\java.exe" set PATH=%JAVA_BIN%;%PATH%

for %%L in (squadratinhos squadrats) do (
    set "LAYER=%%L"
    echo !LAYER!
	
	ogr2ogr -f GeoJSON -t_srs EPSG:4326 "%BUILD%\!LAYER!_wgs84.geojson" "%BUILD%\trophies.gpkg" "!LAYER!" -nlt PROMOTE_TO_MULTI
	
	python geojson2osm.py ^
		--in "%BUILD%\!LAYER!_wgs84.geojson" ^
		--out "%BUILD%\!LAYER!.osm" ^
		--no-default-index-tag ^
		--add-index-tag landuse=!LAYER! ^
		--duplicate-outer-tags
	
	pushd "%MC_DIR%"
	call utilities.bat generate-map "%CD%\%BUILD%\!LAYER!.osm" --rendering-types="%CD%\rendering_types_!LAYER!.xml"
	popd
)

endlocal
