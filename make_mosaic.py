#!/usr/bin/python
import numpy as np
from astropy.io import fits
from common.util import get_mosaic_coordinate, get_path
from helpers.helper_config import HelperConfig, check_for_files
from common.logger import get_logger

__author__ = 'S. Federici (DESY)'
__version__ = '0.1.0'


class MakeMosaic:
    def __init__(self, obs, mosaic_conf):
        """
        Generate 'unabsorbed HI','HISA', and HI CGPS-like mosaics
        """
        self.survey = obs.survey
        self.mosaic = obs.mosaic
        self.species = obs.species
        self.type = obs.type

        self.logger = get_logger(self.survey + '_' + self.mosaic + '_' + self.species + '_GenerateMosaic')
        self.helper = HelperConfig(self.survey, self.species, self.mosaic)

        path = get_path(key="lustre_%s_%s" % (self.survey.lower(), self.species.lower()))
        if self.species == 'HI+HISA':
            path = get_path(key='lustre_' + self.survey.lower() + '_hi')
        if self.survey == 'Galprop':
            self.mosaic = mosaic_conf['mosaic']
        if self.survey == 'Dame':
            path = get_path(key="lustre_dame")
            self.mosaic = mosaic_conf['mosaic']

        flag = self.species + '_line.fits'
        if self.survey == 'LAB':
            flag = self.species + '_line_image.fits'

        file = path + self.survey + '_' + self.mosaic + '_' + flag
        check_for_files([file], existence=True)
        self.filename = file

        self.logger.info('Getting the data from {}'.format(obs.filename))

        if self.survey not in ['CGPS', 'SGPS', 'VGPS']:
            self.mosaic = mosaic_conf['mosaic']
            lon = mosaic_conf['lon']  # deg
            lat = mosaic_conf['lat']  # deg
            z1 = mosaic_conf['z1']  # m/s or kpc
            z2 = mosaic_conf['z2']  # m/s or kpc
            side = mosaic_conf['side']

            if z1 == 'INDEF' and z2 == 'INDEF':
                z1 = np.amin(obs.zarray)
                z2 = np.amax(obs.zarray)
            else:
                z1 = float(z1)
                z2 = float(z2)
            z1_px = int(np.ceil(obs.pz - 1. + (z1 - obs.z) / obs.dz))
            z2_px = int(np.ceil(obs.pz - 1. + (z2 - obs.z) / obs.dz))

            if lon == 'INDEF' and lat == 'INDEF':
                lon = obs.x
                lat = obs.y
            else:
                lon = float(lon)  # deg
                lat = float(lat)  # deg

            if side == 'INDEF':
                side = np.fabs(obs.nx * obs.dx)
            else:
                side = float(side) / 2.  # deg

            l, b, sign = get_mosaic_coordinate(obs, self.survey, lon, lat, side)

            if self.survey != 'Dame':
                z = [z1_px, z2_px]
                # Order indexes
                if z1_px > z2_px:
                    z = [z2_px, z1_px]

            crpix1 = int(round((l[1] - l[0]) / 2.))
            crpix2 = int(round((b[1] - b[0]) / 2.))

            self.logger.info("Mosaic properties:")
            self.logger.info("- (l0,b0) = (%.3f,%.3f) deg, [%s,%s] px" % (lon, lat, l[0] + crpix1, b[0] + crpix2))
            if self.survey == 'Galprop':
                self.logger.info("- (r1,r2) = (%.2f,%.2f) px" % (z[0], z[1]))
            elif self.survey == 'LAB' or self.survey == 'SGPS':
                self.logger.info("- (v1,v2) = (%.3f,%.3f) m/s, [%s,%s] px" % (z1, z2, z[0], z[1]))
            self.logger.info("- (h0,w0) = (%s,%s) deg, [%s,%s] px" % (side, side, crpix1, crpix2))

            if self.survey != 'Dame':
                # The third axes can not be negative then I need to increase the index on the right z[1] by 1
                # in order to match the size of the origianl axes
                if z[0] == 0:
                    z[0] = 1
                    z[1] = z[1] + 1

            newmosaic = ''
            if self.survey == 'Dame':
                newmosaic = obs.observation[b[0]:b[1], l[0]:l[1]]
            if self.survey == 'LAB':
                newmosaic = obs.observation[z[0] - 1:z[1], b[0]:b[1], l[0]:l[1]]
            if self.survey == 'SGPS':
                newmosaic = obs.observation[:, z[0] - 1:z[1], b[0]:b[1], l[0]:l[1]]
            if self.survey == 'Galprop':
                newmosaic = obs.observation[z[0] - 1:z[1], b[0]:b[1], l[0]:l[1]]
                # Revert the longitude
                newmosaic = newmosaic[:, :, ::-1]  # sintax [::-1] = [start:stop:step]
                obs.dx = sign[0] * obs.dx
                obs.dy = sign[1] * obs.dy

            # Write new header
            newheader = fits.Header()
            newheader["ctype1"] = ("GLON-CAR", "Coordinate type")
            newheader["crval1"] = (lon, "Galactic longitude of reference pixel")
            newheader["crpix1"] = (crpix1, "Reference pixel of lon")
            newheader["cdelt1"] = (obs.dx, "Longitude increment")
            newheader["crota1"] = (obs.keyword["crota1"], "Longitude rotation")
            newheader["cunit1"] = ("deg", "Unit type")
            newheader["ctype2"] = ("GLAT-CAR", "Coordinate type")
            newheader["crval2"] = (lat, "Galactic latitude of reference pixel")
            newheader["crpix2"] = (crpix2, "Reference pixel of lat")
            newheader["cdelt2"] = (obs.dy, "Latitude increment")
            newheader["crota2"] = (obs.keyword["crota2"], "Latitude rotation")
            newheader["cunit2"] = ("deg", "Unit type")

            if self.survey == 'Dame':
                newheader["bunit"] = ("K km s-1", "Map units")

            if self.survey == 'Galprop':
                newheader["ctype3"] = ("RingBand", "Coordinate type")
                newheader["crval3"] = (obs.zarray[z[0] - 1], "Ring of reference pixel")
                newheader["crpix3"] = (1, "Reference pixel of ring")
                newheader["cdelt3"] = (obs.dz, "Ring increment")
                newheader["crota3"] = (obs.keyword["crota3"], "Ring rotation")
                newheader["cunit3"] = ("ring num", "Unit type")
                newheader["bunit"] = ("K km s-1", "Map units")
            elif self.survey == 'LAB' or self.survey == 'SGPS':
                newheader["ctype3"] = ("VELO-LSR", "Coordinate type")
                newheader["crval3"] = (obs.zarray[z[0] - 1], "Velocity of reference pixel")
                newheader["crpix3"] = (1, "Reference pixel of vel")
                newheader["cdelt3"] = (obs.dz, "Velocity increment")
                newheader["crota3"] = (obs.keyword["crota3"], "Velocity rotation")
                newheader["cunit3"] = ("m/s", "Unit type")
                newheader["bunit"] = ("K", "Map units")

            newheader["system"] = ("GALACTIC", "Coordinate system")
            newheader["equinox"] = (2000., "Equinox of ref. coord.")
            newheader["datamin"] = (np.amin(newmosaic), "Min value")
            newheader["datamax"] = (np.amax(newmosaic), "Max value")
            newheader["object"] = (self.survey + " Mosaic " + self.mosaic, self.survey + " Mosaic")

            if self.survey in ['LAB', 'SGPS']:
                newheader["band"] = (obs.keyword["band"], "Rest frequency in Hz")

            results = fits.PrimaryHDU(newmosaic, newheader)
        else:
            # Get emission data and velocity interval
            Tb = obs.observation[:, :, :, :]
            dv = np.fabs(obs.dz / 1000.)  # [velocity] = km s-1
            vel = obs.zarray / 1000.
            zmin = obs.zmin
            zmax = obs.zmax

            # free memory
            del obs.observation
            del obs.zarray

            if self.species != 'CO':
                if self.species == 'HISA':
                    Tb = np.zeros(Tb.shape, dtype=np.float32)

                path_data = get_path(key='{}_hisa_dat'.format(self.survey.lower()))
                datafile = path_data + self.survey + '_' + self.mosaic + '_HISA.dat'
                check_for_files([datafile])
                input = open(datafile, "r")
                lines = input.readlines()

                xdim = Tb.shape[3]
                ydim = Tb.shape[2]

                # print Tb.shape[1],ydim,xdim
                for line in lines:
                    na = float(line.split('\n')[0].split()[0])  # HISA region
                    nb = float(line.split('\n')[0].split()[1])  # HISA location
                    nc = float(line.split('\n')[0].split()[2])  # Unabsorbed brightness (Tu) Tb only HI
                    nd = float(line.split('\n')[0].split()[3])  # Delta T (always negative)  Tb only HISA
                    # print "%.2f\t%.2f\t%.2f\t%.2f"%(na,nb,nc,nd)

                    # m = floor(nb/1024/1024)
                    # ha = nb-m*1024*1024
                    # l = floor(ha/1024)
                    # k = ha-l*1024
                    # print m,l,k

                    m = np.floor(nb / xdim / ydim)
                    ha = nb - m * xdim * ydim
                    l = np.floor(ha / xdim)
                    k = ha - l * xdim

                    if self.species == 'HISA':
                        Tb[0, m, l, k] = np.fabs(nd)
                    elif self.species == 'HI_unabsorbed':
                        Tb[0, m, l, k] = nc
                        # elif self.species == 'HI+HISA':
                        #	Tb[0,m,l,k] = nc + fabs(nd)
            else:
                self.logger.error('This function can be only applied to HI_unabsorbed and HISA mosaics.')

            obs.keyword['datamin'] = np.amin(Tb)
            obs.keyword['datamax'] = np.amax(Tb)

            obs.keyword['minfil'] = np.unravel_index(np.argmin(Tb), Tb.shape)[1]
            obs.keyword['mincol'] = np.unravel_index(np.argmin(Tb), Tb.shape)[2]
            obs.keyword['minrow'] = np.unravel_index(np.argmin(Tb), Tb.shape)[3]

            obs.keyword['maxfil'] = np.unravel_index(np.argmax(Tb), Tb.shape)[1]
            obs.keyword['maxcol'] = np.unravel_index(np.argmax(Tb), Tb.shape)[2]
            obs.keyword['maxrow'] = np.unravel_index(np.argmax(Tb), Tb.shape)[3]

            # results = fits.CompImageHDU(Tb[0],obs.keyword,'image')
            results = fits.PrimaryHDU(Tb, obs.keyword)
        # results.scale('int16', '', bscale=obs.bscale, bzero=obs.bzero)

        # Output file
        self.logger.info('Writing data to a fits file in...')
        results.writeto(file, output_verify='fix')
        self.logger.info('{}'.format(path))
        self.logger.info('Done')
