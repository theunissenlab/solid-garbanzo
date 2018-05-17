import os
import sys

import numpy as np
from PyQt5 import QtWidgets as widgets
from PyQt5.QtCore import Qt

import suss.io
from suss.core import ClusterDataset
from components import (
    ClusterSelector,
    ClusterManipulationOptions,
    ISIPane,
    OverviewScatterPane,
    ProjectionsPane,
    TimeseriesPane,
    WaveformsPane,
    get_color_dict,
    selector_area
)


class App(widgets.QMainWindow):

    def __init__(self):
        super().__init__()
        self.title = "SUSS Viewer"
        self.suss_viewer = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle(self.title)
        mainMenu = self.menuBar()
        fileMenu = mainMenu.addMenu("File")
        load_action = widgets.QAction("Find dataset", self)
        close_action = widgets.QAction("Close", self)
        fileMenu.addAction(load_action)
        fileMenu.addAction(close_action)
        load_action.triggered.connect(self.load_dataset)
        close_action.triggered.connect(self.close)

        self.dataset_loader = DatasetLoader(self)
        self.setCentralWidget(self.dataset_loader)
        self.dataset_loader.main_button.clicked.connect(self.load_dataset)
        self.dataset_loader.quit_button.clicked.connect(self.close)

        rect = self.frameGeometry()
        center = widgets.QDesktopWidget().availableGeometry().center()
        rect.moveCenter(center)
        self.move(rect.topLeft())

        self.show()
            
    def load_dataset(self):
        options = widgets.QFileDialog.Options()
        options |= widgets.QFileDialog.DontUseNativeDialog
        self.selected_file, _ = widgets.QFileDialog.getOpenFileName(
            self,
            "Load dataset",
            ".",
            "(*.pkl)",
            options=options)
        if not self.selected_file:
            return
        else:
            loading = widgets.QLabel(self)
            loading.setText("Loading {}".format(self.selected_file))
            loading.setAlignment(Qt.AlignCenter)
            self.setCentralWidget(loading)
            self.resize(1200, 600)
            self.show()
            dataset = suss.io.read_pickle(self.selected_file)
            self.suss_viewer = SussViewer(dataset, self)
            self.setCentralWidget(self.suss_viewer)
            self.resize(1200, 600)
            self.show()

    def save_dataset(self, dataset):
        options = widgets.QFileDialog.Options()
        options |= widgets.QFileDialog.DontUseNativeDialog

        part1, part2 = self.selected_file.split("_")
        _, part2 = part2.split("-")
        default_name = "{}curated{}".format(part1, part2)

        file_name, _ = widgets.QFileDialog.getSaveFileName(
            self,
            "Save dataset",
            default_name,
            "(*.pkl)",
            options=options)
        if not file_name:
            return
        else:
            suss.io.save_pickle(file_name, dataset)
            widgets.QMessageBox.information(self, "Save", "Successfully saved {} to {}".format(dataset, file_name))



class DatasetLoader(widgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = widgets.QVBoxLayout(self)
        self.main_button = widgets.QPushButton("Load Dataset", self)
        self.quit_button = widgets.QPushButton("Quit", self)
        layout.addWidget(self.main_button)
        layout.addWidget(self.quit_button)
        self.setLayout(layout)


class SussViewer(widgets.QFrame):

    def __init__(self, dataset=None, parent=None):
        super().__init__(parent)
        self.original_dataset = dataset
        self.dataset = dataset
        self.active_clusters = set()
        self.setup_panes()

    def setup_panes(self):
        color_dict = get_color_dict(self.dataset.labels)
        self.projections = ProjectionsPane(self.dataset, color_dict, size=(300, 350), facecolor="#666666")
        self.overview = OverviewScatterPane(self.dataset, color_dict, size=(100, 100), facecolor="#444444")
        self.timeseries = TimeseriesPane(self.dataset, color_dict, size=(700, 100), facecolor="#888888")
        self.waveforms = WaveformsPane(self.dataset, color_dict, size=(300, 250), facecolor="#444444")
        self.isi = ISIPane(self.dataset, color_dict, size=(200, 100), facecolor="#444444")
        self.cluster_selector = ClusterSelector(self.dataset, color_dict, self.toggle)
        self.actions_panel = ClusterManipulationOptions(
            reset_cb=self.reset,
            clear_cb=self.clear,
            merge_cb=self.merge,
            save_cb=self.save,
        )

        # scroll_area = selector_area(self.dataset, 140, color_dict, self.toggle)

        outer_2 = widgets.QHBoxLayout()
        outer_1 = widgets.QVBoxLayout()
        inner_1 = widgets.QHBoxLayout()
        inner_2 = widgets.QVBoxLayout()
        inner_3 = widgets.QHBoxLayout()
        inner_1.addWidget(self.projections)
        inner_3.addWidget(self.isi)
        inner_3.addWidget(self.overview)
        inner_2.addLayout(inner_3)
        inner_2.addWidget(self.waveforms)
        inner_1.addLayout(inner_2)
        outer_1.addLayout(inner_1)
        outer_1.addWidget(self.timeseries)
        outer_2.addWidget(self.cluster_selector)
        outer_2.addLayout(outer_1)
        outer_2.addWidget(self.actions_panel)

        self.setLayout(outer_2)

    def reset(self):
        self.dataset = self.original_dataset
        self.clear()
        self.dataset_updated()

    def clear(self):
        self.active_clusters = set()
        self.set_active()

    def merge(self):
        if len(self.active_clusters) < 2:
            widgets.QMessageBox.warning(self, "Merge failed", "Not enough clusters selected to merge")
            return

        new_cluster = self.dataset.select(
            np.isin(
                self.dataset.labels,
                list(self.active_clusters)
            )
        )
        complement = new_cluster.complement

        self.dataset = ClusterDataset(
            np.concatenate([
                [new_cluster.flatten(1)],
                complement.nodes
            ]),
            labels=np.concatenate([
                [new_cluster.labels[0]],
                complement.labels
            ])
        )
        self.active_clusters = set([new_cluster.labels[0]])
        self.dataset_updated()

    def save(self):
        self.parent().save_dataset(self.dataset)

    def toggle(self, selected, label=None):
        if selected:
            self.active_clusters.add(label)
        else:
            self.active_clusters.remove(label)
        self.set_active()

    def dataset_updated(self):
        self.projections.dataset = self.dataset
        self.overview.dataset = self.dataset
        self.timeseries.dataset = self.dataset
        self.waveforms.dataset = self.dataset
        self.isi.dataset = self.dataset
        self.cluster_selector.dataset = self.dataset
        self.projections.setup_data()
        self.overview.setup_data()
        self.timeseries.setup_data()
        self.waveforms.setup_data()
        self.isi.setup_data()
        self.cluster_selector.setup_data()
        self.set_active()

    def set_active(self):
        self.projections.update_selection(self.active_clusters)
        self.overview.update_selection(self.active_clusters)
        self.timeseries.update_selection(self.active_clusters)
        self.waveforms.update_selection(self.active_clusters)
        self.isi.update_selection(self.active_clusters)
        self.cluster_selector.update_selection(self.active_clusters)


if __name__ == "__main__":
    app = widgets.QApplication(sys.argv)
    window = App()
    sys.exit(app.exec_())

