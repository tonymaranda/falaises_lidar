# This Python file uses the following encoding: utf-8

__desc__ = 'Script principal pour extraire les falaises a partir des donnees lidar du MFFP'
__author__ = 'Antoine Maranda tonymaranda@gmail.com'
__version__ = '1.0.1'
__date__ = '2020-07-13'
__update__ = ''

import os
import pandas as pd
import geopandas as gpd
import numpy as np
import rasterio
import gdal
from shapely.geometry import shape
from rasterstats import zonal_stats
import fiona
fiona.supported_drivers['KML'] = 'rw'
import wget
import datetime


## variables:
dossier="F:\GL_Antoine\webmap" ### working directory
min_slope = 70  ### valeur de pente minimale pour etre identifi� comme un cliff (en degr�s)
surface_min = 100 ### surface minimale pour �tre consid�r� comme une falaise int�ressante (en metres carr�s)
hauteur_min = 20 ### hauteur minimale pour �tre ocnsid�r�e comme une falaise int�ressante (en m�tres)
region=fr"{dossier}\region_proj.shp"  ## path vers le shapes de regions
index=fr"{dossier}\Index_MNT20k.shp" ### path vers index des feuillets
geol=fr"{dossier}\geol_simple.shp" ### path vers le fichier des zones geologiques du Quebec
carriere= fr"{dossier}\carrieres.shp" ### path vers le fichier des carrieres du Quebec
distance_carriere=1000 ### distance minimale d une carriere pour etre consid�r�e comme une falaise

### selection par region administrative ou shapefile custom
regions_a_traiter=['12'] ### num�ro des r�gions administrative � traiter
custom_shape=["F:\GL_Antoine\webmap\clip.shp"] #### path vers les shapefile custom
type_process='shape'   ### DOIT ETRE 'shape' ou 'region'


if type_process=='region':
    
    for r in regions_a_traiter:

        dest_folder = fr'{dossier}\{r}'  ### path pour fichier de destination (doit pouvoir contenir envrion 5Gb)
        print('processing region {}...'.format(r))
        
        os.makedirs(dest_folder, exist_ok=True)
        
        # liste de feuillet deja traites ou downloade,  si jamais le script ou  le FTP plante en cours de route
        liste=os.listdir(dest_folder)
        liste_fait=[]
        liste_download=[]
        for f in liste:
            if f [-4:] == '.shp':
                f=f.split('_')[-1]
                f=f[:-4]
                liste_fait.append(f)
            elif f [-4:] == '.tif':
                f=f.split('_')[-1]
                f=f[:-4]
                liste_download.append(f)
            else:
                continue      
        region=gpd.read_file(region)
        
        region=region[region['RES_CO_REG']==r]
              
        index=gpd.read_file(index)
        
        tiles=gpd.overlay(index, region, how='intersection')
    

elif type_process=='shape':
    
    for shapefile in custom_shape:
        r=shapefile.split('\\')[-1].replace('.shp', '')
        dest_folder = fr'{dossier}\{r}'  ### path pour fichier de destination (doit pouvoir contenir envrion 5Gb)
        print('processing shapefile {}...'.format(r))
        os.makedirs(dest_folder, exist_ok=True)
        
        # liste de feuillet deja traites ou downloade,  si jamais le script ou  le FTP plante en cours de route
        liste=os.listdir(dest_folder)
        liste_fait=[]
        liste_download=[]
        for f in liste:
            if f [-4:] == '.shp':
                f=f.split('_')[-1]
                f=f[:-4]
                liste_fait.append(f)
            elif f [-4:] == '.tif':
                f=f.split('_')[-1]
                f=f[:-4]
                liste_download.append(f)
            else:
                continue        
        region=gpd.read_file(shapefile)
        region=region.to_crs({'init': 'epsg:4326'})
        index=gpd.read_file(index)
        tiles=gpd.overlay(index, region, how='intersection')

else:
    print('!!"type_process" variable must be "shape" or "region"!!')

start_timer = datetime.datetime.now()

tiles=tiles['No_tuile2']
 
print('total of {} tiles to process'.format(len(tiles)))
count_tile=0
  
## pour chaque feuillet a linterieur de la region
for t in tiles:
    start_timer_tile = datetime.datetime.now()
    t_1=str(t[:-3])
    t_2=t[-3:]
    #print(t_2)
    if t_2=='202':
        t_2='NE'
    elif t_2=='201':
        t_2 = 'NO'
    elif t_2 == '102':
        t_2 = 'SE'
    elif t_2 == '101':
        t_2 = 'SO'
    else:
        print('weird')
        pass
    feuillet=t_1+t_2
      
    ### verification de disponibilit� et download du MNT
    print('processing tile {}...'.format(feuillet))
    link ='ftp://transfert.mffp.gouv.qc.ca/Public/Diffusion/DonneeGratuite/Foret/IMAGERIE/Produits_derives_LiDAR/{}/{}/MNT_{}.tif'.format(feuillet[:3], feuillet, feuillet)  ### lien vers le MNT lidar du MFFP
  
    if feuillet in liste_fait:
        print(' {} deja fait'.format(feuillet))
        continue
    else:
        if feuillet not in liste_download:
            try:
                print('downloading file MNT_{}.tif....'.format(feuillet))
                wget.download(link, out=r'{}\MNT_{}.tif'.format(dest_folder, feuillet))
            except:
                print('mnt pas disponible')
                continue
        else:
            print('mnt deja download, processing...')
            pass
  
        print('mnt disponible, processing.... ')
        count_tile = count_tile + 1
        mnt = r'{}\MNT_{}.tif'.format(dest_folder, feuillet)
          
        ## calcul de pente et des orientations de pente
        slopes = os.path.join(dest_folder, 'slopes.tif')
        aspect= os.path.join(dest_folder, 'aspect.tif')
        gdal.DEMProcessing(slopes, mnt, "slope")
        gdal.DEMProcessing(aspect, mnt, "aspect")
          
        ## identidfication des portion avec une pente assez prononc�e pour �tre consdid�r�e comme une falaise
        raster = rasterio.open(slopes)
        band = raster.read(1)
  
        band = band.clip((min_slope-1), min_slope)
  
        band[band == (min_slope-1)] = 0
        band[band == min_slope] = 1
  
        print(len(band[band==1]))
  
        if len(band[band==1]) == 0:
            print('no slope of more than {} degrees identified in tile {}, skipping'.format(feuillet, min_slope))
            raster.close()
            os.remove(slopes)
            os.remove(aspect)
            os.remove(mnt)
            continue
  
        mask = band != 0
          
        ## retrait des petits bouts de falaises insignifiants
  
        mypoly = []
        for vec in rasterio.features.shapes(band, mask=mask, transform=raster.transform):
            mypoly.append(shape(vec[0]))
  
        gdf = gpd.GeoDataFrame(mypoly, crs=raster.crs)
  
        gdf = gdf.rename(columns={0: "geometry"})
  
        gdf['surface'] = gdf['geometry'].area
  
        gdf = gdf[gdf['surface'] > surface_min]
  
        if len(gdf) == 0:
            print('no large cliffs identified in tile {}, skipping'.format(feuillet))
            raster.close()
            os.remove(slopes)
            os.remove(aspect)
            os.remove(mnt)
            continue
  
        ## retrait des falaises pas assez hautes
        gdf['hauteur'] = np.nan
        count = 0
  
        for f in range(len(gdf)):
            count = count + 1
            count_low = count - 1
            feature = gdf.iloc[f, 0]
            minimum = zonal_stats(feature, mnt, stats=['min', 'max'], nodata='0', all_touched=True)
            height = minimum[0]['max'] - minimum[0]['min']
            gdf.iloc[f, 2] = height
  
        gdf = gdf[gdf['hauteur'] > hauteur_min]
        gdf['surface'] = gdf['surface'].round(3)
        gdf['hauteur'] = gdf['hauteur'].round(3)
  
        if len(gdf) == 0:
            print('no high cliffs identified in tile {}, skipping'.format(feuillet))
            raster.close()
            os.remove(slopes)
            os.remove(aspect)
            os.remove(mnt)
            continue
  
        print('{} cliffs identified'.format(len(gdf)))
          
        ## identification de l'orientaiton des falaises
        gdf['orientation'] = np.nan
        count = 0
  
        for f in range(len(gdf)):
            count = count + 1
            count_low = count - 1
            feature = gdf.iloc[f, 0]
            aspect_cat = zonal_stats(feature, aspect, stats=['median'], nodata='0', all_touched=True)
            def cat(x):
                if x >= 337.5 and x < 360:
                    return 'N'
                if x >= 0 and x < 22.5:
                    return 'N'
                if x >= 22.5 and x < 67.5:
                    return 'NE'
                if x >= 67.5 and x < 112.5:
                    return 'E'
                if x >= 112.5 and x < 157.5:
                    return 'SE'
                if x >= 157.5 and x < 202.5:
                    return 'S'
                if x >= 202.5 and x < 247.5:
                    return 'SO'
                if x >= 247.5 and x < 292.5:
                    return 'O'
                if x >= 292.5 and x < 337.5:
                    return 'NO'
                else:
                    return 'NaN'
            value=round((aspect_cat[0]['median']), 3)
            value=cat(value)
            gdf.iloc[f, 3] = value
          
        ## calcul de la pente moyenne
        gdf['pente_moyenne'] = np.nan
        count = 0
  
        for f in range(len(gdf)):
            count = count + 1
            count_low = count - 1
            feature = gdf.iloc[f, 0]
            av_slope = zonal_stats(feature, slopes, stats=['mean'], nodata='0', all_touched=True)
            av_slope = av_slope[0]['mean']
            gdf.iloc[f, 4] = av_slope
          
        ## extraction du feuillet en shapefile et kml
        gdf.to_file(os.path.join(dest_folder, 'falaises_region_{}.shp'.format(feuillet)), driver='ESRI Shapefile')
        gdf.to_file(os.path.join(dest_folder, 'falaises__region_{}.kml'.format(feuillet)), driver='KML')
  
        raster.close()
        os.remove(slopes)
        os.remove(aspect)
        os.remove(mnt)
        end_timer_tile = datetime.datetime.now()
        time_elapsed_tile = end_timer_tile - start_timer_tile
 
        print(f'tile {feuillet} processed in {time_elapsed_tile}, {(len(tiles) - count_tile)} tiles remaining...')
  
 
## joindre tous les feuillet de la region en un seul gdf 
liste_shp=os.listdir(dest_folder)
count=0
for f in liste_shp:
    if f[-3:]=='shp':
        count=count+1
        path=os.path.join(dest_folder, f)
        gdf=gpd.read_file(path)
        gdf = gdf.to_crs({'init': 'epsg:4326'})
        if count == 1:
            gdf_all = gdf
        else:
            gdf_all = pd.concat([gdf_all, gdf], sort=False)
    else:
        continue
        
### clip avec les limites de la région ou du shape
gdf_all=gpd.overlay(gdf_all, region, how='intersection')
 
### enlever les carrieres  
print('removing quarries...')   
carriere_gdf=gpd.read_file(carriere)
carriere_gdf=gdf.to_crs({'init': 'epsg:32618'})
buff=gdf.buffer(distance_carriere)
buff=gpd.GeoDataFrame(gpd.GeoSeries(buff), crs={'init': 'epsg:32618'})
buff= buff.rename(columns={0:'geometry'}).set_geometry('geometry')
buff=buff.to_crs({'init': 'epsg:4326'})
gdf_all = gpd.overlay(gdf_all, buff, how="difference")
geol_gdf=gpd.read_file(geol) 
geol_gdf=geol_gdf.to_crs({'init': 'epsg:4326'})
 
### joindre le type de roche
print('joining geology info...')
gdf_all = gpd.sjoin(gdf_all, geol_gdf, how="inner", op='intersects')
 
### enregistrer le tout en shapefile et KML
print('saving all tiles in one shapefile...')
gdf_all.to_file(os.path.join(dest_folder, 'falaises_region_{}.shp'.format(r)), driver='ESRI Shapefile') 
gdf_all.to_file(os.path.join(dest_folder, 'falaises__region_{}.kml'.format(r)), driver='KML')

end_timer = datetime.datetime.now()
time_elapsed = end_timer - start_timer
print(f'Cliffs identified for region {r} in {time_elapsed}')

quit()
