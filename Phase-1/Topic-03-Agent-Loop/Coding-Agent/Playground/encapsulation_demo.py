class BankAccount:
    def __init__(self, owner, balance=0):
        self.__owner = owner  # private attribute
        self.__balance = balance  # private attribute

    def deposit(self, amount):
        if amount > 0:
            self.__balance += amount
            print(f'Deposited: {amount}')
        else:
            print('Deposit amount must be positive')

    def withdraw(self, amount):
        if 0 < amount <= self.__balance:
            self.__balance -= amount
            print(f'Withdrawn: {amount}')
        else:
            print('Invalid withdrawal amount')

    def get_balance(self):
        return self.__balance

    def get_owner(self):
        return self.__owner

# Demonstration of the BankAccount class
if __name__ == '__main__':
    account = BankAccount('Alice', 100)
    print(f'Account Owner: {account.get_owner()}')
    print(f'Initial Balance: {account.get_balance()}')
    account.deposit(50)
    print(f'Updated Balance: {account.get_balance()}')
    account.withdraw(30)
    print(f'Final Balance: {account.get_balance()}')
    account.withdraw(150)  # Trying to withdraw more than balance