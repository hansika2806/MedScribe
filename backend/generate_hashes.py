from passlib.context import CryptContext

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

print('DR_SHARMA_PASSWORD_HASH=' + pwd_context.hash('medscribe123'))
print('DR_KUMAR_PASSWORD_HASH=' + pwd_context.hash('medscribe123'))
print('DR_PATEL_PASSWORD_HASH=' + pwd_context.hash('medscribe123'))

# Made with Bob
