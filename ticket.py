class Ticket:
    def __init__(self, key, description):
        self.key = key
        self.description = description

    def to_dict(self):
        return {
            "key": self.key, 
            "description": self.description
            }

t = Ticket("TMA-1", "probleme de connexion")
print(t.to_dict())
