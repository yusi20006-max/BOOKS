from books.physical import Location


def test_location_can_identify_building_and_room():
    x=Location("loc1","خانه","اتاق مطالعه")
    assert (x.building,x.room)==("خانه","اتاق مطالعه")
