from regression_firewall.sqlshape import sql_shape, write_targets


def test_parameters_dont_change_the_shape():
    assert sql_shape("SELECT * FROM users WHERE id = 42") == \
        sql_shape("SELECT * FROM users WHERE id = 7")
    assert sql_shape("SELECT * FROM users WHERE name = 'alice'") == \
        sql_shape("SELECT * FROM users WHERE name = 'bob'")


def test_string_numeric_literals_become_placeholders():
    shape = sql_shape("INSERT INTO logs(msg, code) VALUES ('hi', 3)")
    assert shape == "INSERT INTO logs(msg, code) VALUES (?, ?)"


def test_whitespace_and_comments_collapse():
    a = sql_shape("SELECT  a,\n  b -- trailing\nFROM t WHERE x = 1")
    b = sql_shape("SELECT a, b FROM t WHERE x = 2")
    assert a == b


def test_in_list_collapses_regardless_of_length():
    a = sql_shape("SELECT * FROM t WHERE id IN (1, 2, 3)")
    b = sql_shape("SELECT * FROM t WHERE id IN (1)")
    assert a == b == "SELECT * FROM t WHERE id IN (?)"


def test_block_comments():
    assert sql_shape("SELECT /* secret */ 1") == sql_shape("SELECT 2")


def test_deterministic():
    q = "UPDATE accounts SET balance = 99.5 WHERE id = 'x'"
    assert sql_shape(q) == sql_shape(q)


def test_write_targets():
    assert write_targets("INSERT INTO users(name) VALUES (?)") == {"users"}
    assert write_targets("INSERT OR REPLACE INTO cache(k) VALUES (?)") == {"cache"}
    assert write_targets("UPDATE accounts SET a = 1") == {"accounts"}
    assert write_targets("DELETE FROM sessions") == {"sessions"}
    assert write_targets("CREATE TABLE IF NOT EXISTS meta(id)") == {"meta"}
    assert write_targets("DROP TABLE IF EXISTS old") == {"old"}
    assert write_targets("SELECT * FROM users") == set()


def test_number_inside_identifier_untouched():
    # sha256-like column names must not lose digits
    shape = sql_shape("SELECT sha256 FROM blobs WHERE id2 = 1")
    assert "sha256" in shape and "id2" in shape
    assert shape.endswith("WHERE id2 = ?")
