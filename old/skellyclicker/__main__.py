import matplotlib.pyplot as plt
import logging
import os

plt.set_loglevel('WARNING')
logging.getLogger('PIL').setLevel(logging.WARNING)

# https://numexpr.readthedocs.io/en/latest/user_guide.html#threadpool-configuration
# os.environ['NUMEXPR_MAX_THREADS'] = 16
# os.environ['NUMEXPR_NUM_THREADS'] = 16

from skellyclicker.ui.skellyclicker_ui import SkellyClickerUi

if __name__ == "__main__":
    _ui = SkellyClickerUi.create_ui()
    _ui.root.mainloop()
