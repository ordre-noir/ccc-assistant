from ccc_assistant.cog import ExtractImages


def test_images_extractions():
    assert ExtractImages("https://i.imgur.com/0dY8Y1W.jpg").images_urls() == ["https://i.imgur.com/0dY8Y1W.jpg"]
    assert ExtractImages(
        "https://media.discordapp.net/attachments/726754446352056373/1093231767349117028/caudillo.png?width=1424&height=1350").images_urls() == [
               "https://media.discordapp.net/attachments/726754446352056373/1093231767349117028/caudillo.png"]
    assert ExtractImages(
        "https://media.discordapp.net/attachments/726754446352056373/1093231767349117028/caudillo.png "
        "https://images-ext-1.discordapp.net/external/eNDj2RvyeG2zLAc3QJioqI_wzyqXECLhjGwcJizZ2ik/https/media.tenor.com/kBKK4MUC-HoAAAPo/oui"
        "-ouais.mp4 https://cdn.discordapp.com/attachments/1008488496354308199/1095793693912465590/archiviste.png").images_urls() == [
               "https://media.discordapp.net/attachments/726754446352056373/1093231767349117028/caudillo.png",
               "https://cdn.discordapp.com/attachments/1008488496354308199/1095793693912465590/archiviste.png"]
