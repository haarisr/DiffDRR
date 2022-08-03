import torch
import torch.nn as nn

from .projectors.siddon import Siddon
from .utils.backend import get_device
from .utils.camera import Detector


class DRR(nn.Module):
    def __init__(self, volume, spacing, height, delx, width=None, dely=None, device="cpu"):
        """
        Class for generating DRRs.

        Inputs
        ------
        volume : np.ndarray
            CT volume.
        spacing : tuple of float
            The spacing of the volume.
        height : int
            The height of the DRR.
        width : int, optional
            The width of the DRR. If not provided, it is set to `height`.
        delx : float
            The x-axis pixel size.
        dely : float, optional
            The y-axis pixel size. If not provided, it is set to `delx`.
        device : str
            Compute device, either "cpu", "cuda", or "mps".
        """
        super().__init__()
        self.device = get_device(device)

        # Initialize the X-ray detector
        width = height if width is None else width
        dely = delx if dely is None else delx
        self.detector = Detector(height, width, delx, dely, device)

        # Initialize the Projector and register its parameters
        self.siddon = Siddon(volume, spacing, device)
        self.register_parameter("sdr", None)
        self.register_parameter("rotations", None)
        self.register_parameter("translations", None)

    def forward(self, sdr=None, theta=None, phi=None, gamma=None, bx=None, by=None, bz=None):
        """
        Generate a DRR from a particular viewing angle.

        Pass projector parameters to initialize a new viewing angle. If uninitialized, model will
        not run.
        """
        if any(arg is not None for arg in [sdr, theta, phi, gamma, bx, by, bz]):
            self.initialize_parameters(sdr, theta, phi, gamma, bx, by, bz)
        source, rays = self.detector.make_xrays(self.sdr, self.rotations, self.translations)
        drr = self.siddon.raytrace(source, rays)
        return drr

    def initialize_parameters(self, sdr, theta, phi, gamma, bx, by, bz):
        """
        Set the parameters for generating a DRR.

        Inputs
        ------
        Projector parameters:
            sdr   : Source-to-Detector radius (half of the source-to-detector distance)
            theta : Azimuthal angle
            phi   : Polar angle
            gamma : Plane rotation angle
            bx    : X-dir translation
            by    : Y-dir translation
            bz    : Z-dir translation
        return_grads : bool, optional
            If True, return differentiable vectors for rotations and translations
        """
        tensor_args = {"dtype": torch.float32, "device": self.device}
        self.sdr = nn.Parameter(
            torch.tensor(sdr, **tensor_args), requires_grad=False
        )  # Assume that SDR is given for a 6DoF registration problem
        self.rotations = nn.Parameter(torch.tensor([theta, phi, gamma], **tensor_args))
        self.translations = nn.Parameter(torch.tensor([bx, by, bz], **tensor_args))

    def __repr__(self):
        params = [str(param) for param in self.parameters()]
        if len(params) == 0:
            return "Parameters uninitialized."
        else:
            return "\n".join(params)