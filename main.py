import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from custom_validators import Validators
import getpass
from datetime import datetime
import mysql.connector
import streamlit as st  # Import Streamlit
from mysql.connector import Error
from db_config import get_db_connection
from logger import log_db_operation
from decimal import Decimal  # Add this import

class BankManagementSystem:
    def __init__(self):
        self.validators = Validators()
        self.current_user = None

    def clear_screen(self):
        os.system("cls" if os.name == "nt" else "clear")

    def create_account_streamlit(self):
        """Streamlit interface for creating an account."""
        st.title("Create New Account")
        pan = st.text_input("Enter PAN Number (10 characters, format: ABCDE1234F)").strip().upper()
        aadhaar = st.text_input("Enter Aadhaar Number (12 digits)").strip()
        first_name = st.text_input("Enter First Name").strip()
        last_name = st.text_input("Enter Last Name").strip()
        email = st.text_input("Enter Email").strip()
        phone = st.text_input("Enter Phone Number").strip()
        password = st.text_input("Enter Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        submit = st.button("Create Account")

        if submit:
            if not self.validators.validate_pan(pan):
                st.error("Invalid PAN number format!")
                return
            if not self.validators.validate_aadhaar(aadhaar):
                st.error("Invalid Aadhaar number format!")
                return
            if not self.validators.validate_email(email):
                st.error("Invalid email format!")
                return
            if not self.validators.validate_phone(phone):
                st.error("Invalid phone number format!")
                return
            if password != confirm_password:
                st.error("Passwords do not match!")
                return

            hashed_password = self.validators.hash_password(password)
            connection = get_db_connection()
            if connection:
                try:
                    cursor = connection.cursor()
                    query = """
                        INSERT INTO customers 
                        (pan_number, aadhaar_number, first_name, last_name, email, phone_number, password)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """
                    values = (pan, aadhaar, first_name, last_name, email, phone, hashed_password)
                    cursor.execute(query, values)
                    connection.commit()
                    account_number = cursor.lastrowid
                    log_db_operation("Account Creation", f"Account {account_number} created successfully")
                    st.success(f"Account created successfully! Your account number is: {account_number}")
                except mysql.connector.Error as err:
                    if err.errno == 1062:  # Duplicate entry error
                        st.error("This PAN/Aadhaar/Email/Phone is already registered!")
                    else:
                        st.error(f"Error: {err}")
                finally:
                    cursor.close()
                    connection.close()

    def login_streamlit(self):
        if 'user' in st.session_state:
            st.success(f"Already logged in as {st.session_state.user['first_name']} {st.session_state.user['last_name']}")
            return

        st.title("Login")
        account_number = st.text_input("Enter Account Number").strip()
        password = st.text_input("Enter Password", type="password")
        submit = st.button("Login")

        if submit:
            if not account_number.isdigit():
                st.error("Account number should be a number!")
                return

            connection = get_db_connection()
            if connection:
                try:
                    cursor = connection.cursor(dictionary=True)
                    query = "SELECT * FROM customers WHERE customer_account_number = %s"
                    cursor.execute(query, (account_number,))
                    user = cursor.fetchone()

                    if not user:
                        st.error("No account found with the provided account number!")
                        return

                    entered_hash = self.validators.hash_password(password)
                    if entered_hash == user['password']:
                        st.session_state.user = user  # Store user in session state
                        st.success(f"Login successful! Welcome, {user['first_name']} {user['last_name']}!")
                    else:
                        st.error("Invalid password!")
                except mysql.connector.Error as err:
                    st.error(f"Error: {err}")
                finally:
                    cursor.close()
                    connection.close()

    def check_balance_streamlit(self):
        """Streamlit interface for checking balance."""
        if 'user' not in st.session_state:
            st.error("Please login first!")
            return

        connection = get_db_connection()
        if connection:
            try:
                cursor = connection.cursor()
                query = "SELECT balance FROM customers WHERE customer_account_number = %s"
                cursor.execute(query, (st.session_state.user['customer_account_number'],))
                balance = cursor.fetchone()[0]
                st.success(f"Your current balance is: ₹{balance:,.2f}")
            except mysql.connector.Error as err:
                st.error(f"Error: {err}")
            finally:
                cursor.close()
                connection.close()

    def credit_amount_streamlit(self):
        """Streamlit interface for crediting amount."""
        if 'user' not in st.session_state:
            st.error("Please login first!")
            return

        st.title("Credit Amount")
        amount = st.number_input("Enter amount to credit:", min_value=0.0, step=100.0)
        submit = st.button("Credit Amount")

        if submit:
            if amount <= 0:
                st.error("Please enter a valid amount greater than 0!")
                return

            connection = get_db_connection()
            if connection:
                try:
                    cursor = connection.cursor()

                    # Convert amount to Decimal for consistency
                    amount_decimal = Decimal(str(amount))

                    # Update balance
                    update_query = """
                        UPDATE customers 
                        SET balance = balance + %s 
                        WHERE customer_account_number = %s
                    """
                    cursor.execute(update_query, (amount_decimal, st.session_state.user['customer_account_number']))

                    # Get new balance
                    cursor.execute("SELECT balance FROM customers WHERE customer_account_number = %s",
                                   (st.session_state.user['customer_account_number'],))
                    new_balance = cursor.fetchone()[0]

                    # Record transaction
                    transaction_query = """
                       INSERT INTO transactions 
                    (customer_account_number, transaction_type, amount)
                    VALUES (%s, 'credit', %s)
                """
                    cursor.execute(transaction_query, (st.session_state.user['customer_account_number'], amount_decimal))

                    # Get updated balance for display
                    cursor.execute("SELECT balance FROM customers WHERE customer_account_number = %s",
                                 (st.session_state.user['customer_account_number'],))
                    new_balance = cursor.fetchone()[0]
                    connection.commit()
                    st.success(f"₹{float(amount_decimal):,.2f} credited successfully!")
                    st.info(f"Updated balance: ₹{float(new_balance):,.2f}")

                except mysql.connector.Error as err:
                    st.error(f"Error: {err}")
                    connection.rollback()
                finally:
                    cursor.close()
                    connection.close()

    def debit_amount_streamlit(self):
        """Streamlit interface for debiting amount."""
        if 'user' not in st.session_state:
            st.error("Please login first!")
            return

        st.title("Debit Amount")
        amount = st.number_input("Enter amount to debit:", min_value=0.0, step=100.0)
        submit = st.button("Debit Amount")

        if submit:
            if amount <= 0:
                st.error("Please enter a valid amount greater than 0!")
                return

            connection = get_db_connection()
            if connection:
                try:
                    cursor = connection.cursor()

                    # Convert amount to Decimal for consistency
                    from decimal import Decimal
                    amount_decimal = Decimal(str(amount))

                    # Check balance first
                    cursor.execute("SELECT balance FROM customers WHERE customer_account_number = %s",
                                 (st.session_state.user['customer_account_number'],))
                    current_balance = cursor.fetchone()[0]

                    if current_balance < amount_decimal:
                        st.error("Insufficient funds!")
                        return

                    # Update balance
                    update_query = """
                        UPDATE customers 
                        SET balance = balance - %s 
                        WHERE customer_account_number = %s
                    """
                    cursor.execute(update_query, (amount_decimal, st.session_state.user['customer_account_number']))

                    # Record transaction
                    transaction_query = """
                        INSERT INTO transactions 
                        (customer_account_number, transaction_type, amount)
                        VALUES (%s, 'debit', %s)
                    """
                    cursor.execute(transaction_query, (st.session_state.user['customer_account_number'], amount_decimal))

                    # Get updated balance for display
                    cursor.execute("SELECT balance FROM customers WHERE customer_account_number = %s",
                                 (st.session_state.user['customer_account_number'],))
                    new_balance = cursor.fetchone()[0]

                    connection.commit()
                    st.success(f"₹{float(amount_decimal):,.2f} debited successfully!")
                    st.info(f"Updated balance: ₹{float(new_balance):,.2f}")

                except mysql.connector.Error as err:
                    st.error(f"Error: {err}")
                    connection.rollback()
                finally:
                    cursor.close()
                    connection.close()

    def view_transaction_history_streamlit(self):
        """Streamlit interface for viewing transaction history."""
        if 'user' not in st.session_state:
            st.error("Please login first!")
            return

        st.title("Transaction History")
        connection = get_db_connection()
        if connection:
            try:
                cursor = connection.cursor()
                query = """
                    SELECT timestamp, transaction_type, amount 
                    FROM transactions 
                    WHERE customer_account_number = %s 
                    ORDER BY timestamp DESC
                """
                cursor.execute(query, (st.session_state.user['customer_account_number'],))
                transactions = cursor.fetchall()

                if transactions:
                    # Create a DataFrame for better display
                    import pandas as pd
                    df = pd.DataFrame(
                        transactions,
                        columns=['Timestamp', 'Type', 'Amount']
                    )
                    
                    # Format amount column with currency symbol
                    df['Amount'] = df['Amount'].apply(lambda x: f"₹{float(x):,.2f}")
                    
                    # Format timestamp for better readability
                    df['Timestamp'] = pd.to_datetime(df['Timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')

                    # Display transactions with styled DataFrame
                    st.dataframe(
                        df.style.set_properties(**{
                            'text-align': 'left',
                            'font-size': '14px'
                        }).set_table_styles([
                            {'selector': 'th',
                             'props': [('font-weight', 'bold'),
                                       ('text-align', 'left')]}
                        ])
                    )
                else:
                    st.info("No transactions found!")

            except mysql.connector.Error as err:
                st.error(f"Error: {err}")
            finally:
                if connection:
                    cursor.close()
                    connection.close()

def main():
    bank = BankManagementSystem()

    st.sidebar.title("Bank Management System")
    
    # Show logout button if user is logged in
    if 'user' in st.session_state:
        st.sidebar.write(f"Welcome, {st.session_state.user['first_name']}!")
        if st.sidebar.button("Logout"):
            del st.session_state.user
            st.experimental_rerun()

    menu = ["Home", "Create Account", "Login", "Check Balance", 
            "Credit Amount", "Debit Amount", "Transaction History"]
    choice = st.sidebar.selectbox("Menu", menu)

    if choice == "Home":
        st.title("Welcome to the Bank Management System")
        st.write("Use the sidebar to navigate through the application.")
        st.markdown("""
        ### Available Features:
        - Create a new account
        - Login to existing account
        - Check account balance
        - Credit amount
        - Debit amount
        - View transaction history
        """)
    elif choice == "Create Account":
        bank.create_account_streamlit()
    elif choice == "Login":
        bank.login_streamlit()
    elif choice == "Check Balance":
        bank.check_balance_streamlit()
    elif choice == "Credit Amount":
        bank.credit_amount_streamlit()
    elif choice == "Debit Amount":
        bank.debit_amount_streamlit()
    elif choice == "Transaction History":
        bank.view_transaction_history_streamlit()

if __name__ == "__main__":
    main()