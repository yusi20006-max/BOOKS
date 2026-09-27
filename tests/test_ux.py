from books.ux import *

def test_ux_contract():
 c=validate_ux(); assert all((c.rtl,c.mobile,c.keyboard,c.screen_reader,c.consistent_errors,c.recovery_actions))
def test_persian_empty_and_error_states():
 assert "خالی" in empty_state("کتابخانه")["title"]; assert error_state("خطا")["recovery"]=="تلاش دوباره"
