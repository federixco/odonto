"""Archivos generados sin pacientes reales para tests unitarios y WebGL."""
import io
import struct
import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, CTImageStorage


def dicom(z=0, **campos):
    meta = FileMetaDataset()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.MediaStorageSOPClassUID = CTImageStorage
    meta.MediaStorageSOPInstanceUID = f"1.2.826.0.1.3680043.10.1000.{z+1}"
    d = FileDataset(None, {}, file_meta=meta, preamble=b"\0" * 128)
    d.SOPClassUID = CTImageStorage
    d.SOPInstanceUID = meta.MediaStorageSOPInstanceUID
    d.StudyInstanceUID = "1.2.826.0.1.3680043.10.1000.100"
    d.SeriesInstanceUID = "1.2.826.0.1.3680043.10.1000.200"
    d.FrameOfReferenceUID = "1.2.826.0.1.3680043.10.1000.300"
    d.Modality = "CT"
    d.Rows = d.Columns = 64
    d.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
    d.ImagePositionPatient = [0, 0, z]
    d.PixelSpacing = [1, 1]
    d.SliceThickness = 1
    d.SamplesPerPixel = 1
    d.PhotometricInterpretation = "MONOCHROME2"
    d.BitsAllocated = d.BitsStored = 16
    d.HighBit = 15
    d.PixelRepresentation = 1
    d.RescaleSlope = 1
    d.RescaleIntercept = 0
    d.WindowCenter = 300
    d.WindowWidth = 1600
    d.InstanceNumber = z + 1
    pixels = [1000 if (x-32)**2 + (y-32)**2 + ((z-7)*2)**2 < 23**2 else -1000 for y in range(64) for x in range(64)]
    d.PixelData = struct.pack('<' + 'h'*len(pixels), *pixels)
    for k, v in campos.items():
        if v is None:
            delattr(d, k)
        else:
            setattr(d, k, v)
    salida = io.BytesIO()
    d.save_as(salida, enforce_file_format=True)
    return salida.getvalue()


def dicom_multiframe():
    """Tres frames distintos en un objeto SC, solo para navegación de cortes."""
    from pydicom.uid import MultiFrameGrayscaleWordSecondaryCaptureImageStorage
    d = pydicom.dcmread(io.BytesIO(dicom()))
    d.SOPClassUID = d.file_meta.MediaStorageSOPClassUID = MultiFrameGrayscaleWordSecondaryCaptureImageStorage
    d.SOPInstanceUID = d.file_meta.MediaStorageSOPInstanceUID = '1.2.826.0.1.3680043.10.1000.400'
    d.SeriesInstanceUID = '1.2.826.0.1.3680043.10.1000.401'
    d.NumberOfFrames = 3
    d.PixelRepresentation = 0
    d.FrameTime = 100
    d.FrameIncrementPointer = 0x00181063
    pixels = [1200 if (x-32)**2 + (y-32)**2 < radius**2 else 0
              for radius in (8, 16, 24) for y in range(64) for x in range(64)]
    d.PixelData = struct.pack('<' + 'H'*len(pixels), *pixels)
    salida = io.BytesIO()
    d.save_as(salida, enforce_file_format=True)
    return salida.getvalue()


def dicom_rle(z=0):
    """Compresión sin pérdida con el encoder oficial de pydicom, sin NumPy."""
    from pydicom.encaps import encapsulate
    from pydicom.pixels.encoders import RLELosslessEncoder
    from pydicom.uid import RLELossless
    d = pydicom.dcmread(io.BytesIO(dicom(z)))
    d.SeriesInstanceUID = '1.2.826.0.1.3680043.10.1000.500'
    d.SOPInstanceUID = d.file_meta.MediaStorageSOPInstanceUID = f'1.2.826.0.1.3680043.10.1000.501.{z+1}'
    d.PixelData = encapsulate([RLELosslessEncoder.encode(d)])
    d['PixelData'].is_undefined_length = True
    d.file_meta.TransferSyntaxUID = RLELossless
    salida = io.BytesIO()
    d.save_as(salida, enforce_file_format=True)
    return salida.getvalue()


STL = b'''solid sintetico
facet normal 0 0 1
outer loop
vertex 0 0 0
vertex 10 0 0
vertex 0 10 0
endloop
endfacet
facet normal 0 1 0
outer loop
vertex 0 0 0
vertex 0 0 10
vertex 10 0 0
endloop
endfacet
facet normal 1 0 0
outer loop
vertex 0 0 0
vertex 0 10 0
vertex 0 0 10
endloop
endfacet
facet normal 1 1 1
outer loop
vertex 10 0 0
vertex 0 0 10
vertex 0 10 0
endloop
endfacet
endsolid sintetico
'''
PLY = b'''ply
format ascii 1.0
element vertex 4
property float x
property float y
property float z
property uchar red
property uchar green
property uchar blue
element face 4
property list uchar int vertex_indices
end_header
0 0 0 255 0 0
10 0 0 0 255 0
0 10 0 0 0 255
0 0 10 255 255 0
3 0 1 2
3 0 3 1
3 0 2 3
3 1 3 2
'''
