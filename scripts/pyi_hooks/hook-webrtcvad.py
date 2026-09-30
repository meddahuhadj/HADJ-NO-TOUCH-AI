# يطغى على خطّاف pyinstaller-hooks-contrib الذي يبحث عن "webrtcvad"،
# بينما الحزمة المثبتة اسمها webrtcvad-wheels (نفس الوحدة، اسم توزيع مختلف).
from PyInstaller.utils.hooks import copy_metadata

datas = copy_metadata("webrtcvad-wheels")
