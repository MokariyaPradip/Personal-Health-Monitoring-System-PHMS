from controllers import medication_controller


def register_medication_routes(app):
    """Register medication-management routes."""

    @app.route('/medication')
    def medication_page():
        return medication_controller.medication_page()

    @app.route('/add-medication', methods=['POST'])
    @app.route('/addMedication', methods=['POST'])  # legacy alias
    def add_medication():
        return medication_controller.add_medication()

    @app.route('/delete-medication/<int:id>', methods=['DELETE'])
    @app.route('/deleteMedication/<int:id>', methods=['DELETE'])
    def delete_medication(id):
        return medication_controller.delete_medication(id)

    @app.route('/update-medication/<int:id>', methods=['PUT'])
    @app.route('/updateMedication/<int:id>', methods=['PUT'])  # legacy alias
    def update_medication(id):
        return medication_controller.update_medication(id)

    @app.route('/add-medicine', methods=['POST'])
    @app.route('/addMedicine', methods=['POST'])  # legacy alias
    def add_medicine_master():
        return medication_controller.add_medicine_master()

    @app.route('/api/medicine-suggestions', methods=['GET'])
    def api_medicine_suggestions():
        return medication_controller.api_medicine_suggestions()

    @app.route('/api/medicines', methods=['GET'])
    def api_list_medicines():
        return medication_controller.api_list_medicines()
