from tempfile import NamedTemporaryFile

import h5py
import numpy as np
from torch.utils.data import DataLoader

from datasets.hdf5 import HDF5Dataset


class TestHDF5Dataset:
    def test_hdf5_dataset(self):
        path = create_random_dataset((128, 128, 128))

        patch_shapes = [(127, 127, 127), (69, 70, 70), (32, 64, 64)]
        stride_shapes = [(1, 1, 1), (17, 23, 23), (32, 64, 64)]

        phase = 'test'

        for patch_shape, stride_shape in zip(patch_shapes, stride_shapes):
            with h5py.File(path, 'r') as f:
                raw = f['raw'][...]
                label = f['label'][...]

                dataset = HDF5Dataset(path, phase=phase,
                                      slice_builder_config=create_slice_builder(patch_shape, stride_shape),
                                      transformer_config=transformer_config[phase],
                                      raw_internal_path='raw',
                                      label_internal_path='label')

                # create zero-arrays of the same shape as the original dataset in order to verify if every element
                # was visited during the iteration
                visit_raw = np.zeros_like(raw)
                visit_label = np.zeros_like(label)

                for (_, idx) in dataset:
                    visit_raw[idx] = 1
                    visit_label[idx] = 1

                # verify that every element was visited at least once
                assert np.all(visit_raw)
                assert np.all(visit_label)

    def test_hdf5_with_multiple_label_datasets(self):
        path = create_random_dataset((128, 128, 128), label_datasets=['label1', 'label2'])
        patch_shape = (32, 64, 64)
        stride_shape = (32, 64, 64)
        phase = 'train'
        dataset = HDF5Dataset(path, phase=phase,
                              slice_builder_config=create_slice_builder(patch_shape, stride_shape),
                              transformer_config=transformer_config[phase],
                              raw_internal_path='raw',
                              label_internal_path=['label1', 'label2'])

        for raw, labels in dataset:
            assert len(labels) == 2

    def test_hdf5_with_multiple_raw_and_label_datasets(self):
        path = create_random_dataset((128, 128, 128), raw_datasets=['raw1', 'raw2'],
                                     label_datasets=['label1', 'label2'])
        patch_shape = (32, 64, 64)
        stride_shape = (32, 64, 64)
        phase = 'train'
        dataset = HDF5Dataset(path, phase=phase,
                              slice_builder_config=create_slice_builder(patch_shape, stride_shape),
                              transformer_config=transformer_config[phase],
                              raw_internal_path=['raw1', 'raw2'], label_internal_path=['label1', 'label2'])

        for raws, labels in dataset:
            assert len(raws) == 2
            assert len(labels) == 2

    def test_augmentation(self):
        raw = np.random.rand(32, 96, 96)
        # assign raw to label's channels for ease of comparison
        label = np.stack(raw for _ in range(3))

        tmp_file = NamedTemporaryFile()
        tmp_path = tmp_file.name
        with h5py.File(tmp_path, 'w') as f:
            f.create_dataset('raw', data=raw)
            f.create_dataset('label', data=label)
        phase = 'train'
        dataset = HDF5Dataset(tmp_path, phase=phase,
                              slice_builder_config=create_slice_builder((16, 64, 64), (8, 32, 32)),
                              transformer_config=transformer_config[phase])

        # test augmentations using DataLoader with 4 worker threads
        data_loader = DataLoader(dataset, batch_size=1, num_workers=4, shuffle=True)
        for (img, label) in data_loader:
            for i in range(label.shape[0]):
                assert np.allclose(img, label[i])


def create_random_dataset(shape, ignore_index=False, raw_datasets=['raw'], label_datasets=['label']):
    tmp_file = NamedTemporaryFile(delete=False)

    with h5py.File(tmp_file.name, 'w') as f:
        for raw_dataset in raw_datasets:
            f.create_dataset(raw_dataset, data=np.random.rand(*shape))

        for label_dataset in label_datasets:
            if ignore_index:
                f.create_dataset(label_dataset, data=np.random.randint(-1, 2, shape))
            else:
                f.create_dataset(label_dataset, data=np.random.randint(0, 2, shape))

    return tmp_file.name


def create_slice_builder(patch_shape, stride_shape):
    return {
        'name': 'SliceBuilder',
        'patch_shape': patch_shape,
        'stride_shape': stride_shape
    }


transformer_config = {
    'train': {
        'raw': [
            {'name': 'RandomFlip'},
            {'name': 'RandomRotate90'},
            {'name': 'RandomRotate', 'angle_spectrum': 5, 'axes': [[1, 0]]},
            {'name': 'RandomRotate', 'angle_spectrum': 30, 'axes': [[2, 1]]},
            {'name': 'ElasticDeformation', 'spline_order': 3},
            {'name': 'ToTensor', 'expand_dims': True}
        ],
        'label': [
            {'name': 'RandomFlip'},
            {'name': 'RandomRotate90'},
            {'name': 'RandomRotate', 'angle_spectrum': 5, 'axes': [[1, 0]]},
            {'name': 'RandomRotate', 'angle_spectrum': 30, 'axes': [[2, 1]]},
            {'name': 'ElasticDeformation', 'spline_order': 3},
            {'name': 'ToTensor', 'expand_dims': False}
        ]
    },
    'test': {
        'raw': [{'name': 'ToTensor', 'expand_dims': True}],
        'label': [{'name': 'ToTensor', 'expand_dims': False}]
    }
}
